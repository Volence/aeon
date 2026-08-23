# DIRTY-TREE TRIAGE — the 43 uncommitted files in the aeon main working tree

**Date:** 2026-08-22 · **Branch:** `parcel/dirty-tree-triage` · **Main tree at:** `master` `555fb3ff`

The owner's question was not "sort these" but **"why didn't they get added before — are they
just scrap? If not we should keep."** This note answers the *why*, per pile, from evidence.

**Headline: almost none of it is scrap.** 38 of the 43 are a real, coherent, single piece of
the owner's level-authoring work plus its deterministic bake — proven byte-for-byte
reproducible below. They were never committed because **every handoff doc in this repo since
June tells the next session that `games/sonic4/data/editor/**` belongs to an auto-commit
daemon and must not be staged — and that daemon is not running.** The instruction outlived
the mechanism, so the work sat in no-man's-land for three days.

---

## 0. Method and the count

`git status` could not be run against the main tree (this agent is worktree-isolated and git
redirection into the shared checkout is refused). The status was instead **reconstructed**:
`git ls-tree -r master` for the tracked set, a SHA-1 blob hash of every file on disk for the
modified set, and a directory walk plus `git check-ignore` for the untracked set. The main
tree's `HEAD` is `master` = `555fb3ff`, identical to this worktree's base, so the
reconstruction is exact.

**The owner's count of 43 is correct.** Reconstruction reported 45 at first; the extra two
were `.pytest_cache/` and `tools/.pytest_cache/`, which are **self-ignoring** — pytest writes
a nested `.gitignore` containing `*` inside each — so real `git status` never shows them. The
reconstruction missed that only because those directories do not exist in this worktree.
They are not part of the 43 and need no action.

The 43, as `git status --porcelain` renders them (untracked directories collapse to one line):

| count | kind | paths |
|---|---|---|
| 28 | ` M` | `games/sonic4/data/generated/ojz/act1/**` |
| 6 | ` M` | `games/sonic4/data/editor/**` (5 under `ojz/act1/`, plus `ojz_bglib.json`) |
| 4 | ` M` | `games/sonic4/data/collision/*.bin` |
| 1 | `??` | `games/sonic4/data/editor/ojz/act1/export/` (3 files inside) |
| 1 | `??` | `games/sonic4/data/sprites/object-bindings.json` |
| 3 | `??` | `s4.state0`, `s4.debug.state0`, `s4.debug.state1` |

**38 of the 43 are ` M` — tracked files that were committed long ago and are now dirty.** For
those the question is not "why were they never added" but "why are they dirty", which is a
different investigation and is answered in §1.

---

## 1. The main event — one authoring session and its bake (38 files, PILE 2: KEEP)

### What happened, reconstructed from mtimes and content

Every one of the 38 falls into exactly two mtime clusters, and the content diffs tell a single
story:

**2026-08-19 21:42:14 — an Aurora editor save.**
- `ojz_bglib.json`: a **new BG layout was added to the library** —
  `+ {"id": "ingame-forest-v15-1786630615596", "name": "In-game forest (engine v15)"}`.
- `section_0.meta.json`: section 0's `bgLayoutRef` **repointed** from
  `deep-forest-v16-trunks-over-wall-…` to that new `ingame-forest-v15-…`.
- `section_0.objects.json`: the one `solid` object nudged `x 803→808, y 208→210`.

**2026-08-20 13:45:38 — a second Aurora save, painting section 0.**
- `section_0.tiles.bin` (666 bytes differ), `section_0.collattr.bin` (412), and
  `section_0.collattrb.bin` (412) all changed **within the identical byte range
  16609..24351**. One contiguous painted region, tile layout and collision attributes edited
  together. This is hand-authored level design, not a generator artifact.

**2026-08-20 13:45:39-40 — the re-bake fired** (`tools/regenerate-level.sh`; its own header
notes "the editor's edit-look-edit loop re-bakes after every save"), writing
`games/sonic4/data/collision/**` and all 28 files under `games/sonic4/data/generated/ojz/act1/**`.
The collision deltas are confined to shape slots 14-20 (`heightmaps` bytes 224..335,
`angles` 14..20, `solidity` 20) — consistent with the painted region shifting the interned
collision-shape allocation.

### Proof that the generated tree is exactly the bake of the editor edits

Two re-bakes were run **inside this worktree only** (never the main tree), with
`AEON_SKDISASM_DIR=/home/volence/sonic_hacks/skdisasm` and
`AEON_SONIC_HACK_DIR=/home/volence/sonic_hacks/sonic_hack`:

- **Control (A)** — re-bake with the *committed* editor data. Result: the worktree stayed
  clean except `DONOR_PROVENANCE.json`. So the generators are **deterministic**, and the
  committed tree is exactly the bake of the committed editor data.
- **Subject (B)** — the main tree's 6 dirty editor inputs copied in, then re-bake. Compared
  against the main tree's dirty output across `data/generated/ojz/act1/` +
  `data/collision/`: **78 files IDENTICAL, 1 differs, 0 only-on-one-side.** The single
  difference is again `DONOR_PROVENANCE.json`.

`DONOR_PROVENANCE.json` is *supposed* to differ: it stamps the run, not the content — the
donor SHAs, the aeon HEAD, and the dirty-file counts at bake time. The main tree's copy records
`head: 4fda2584` (master at 2026-08-20 11:23) and `mode: "backfill" → "rebake"`.

**Conclusion: the 28 generated + 4 collision files are not stale, not hand-edited, not
corrupted. They are the correct, reproducible bake of the 6 editor edits.**
`verify_level_bin.py` also passed on the re-baked tree
(`act-pool+content+sidecar / local-maps / block-blobs / bininclude-targets / collision-interned / orphans`).

### Are they "regenerable build output" that should be gitignored instead? **No.**

This is the tempting wrong answer and the repo has already ruled against it, twice, in writing:

- `.gitignore` lines 103-115 **explicitly negate** every one of these paths out of the blanket
  `*.bin` — `!games/sonic4/data/generated/**/*.{bin,zx0,emp,asm}`,
  `!games/sonic4/data/collision/**/*.bin`,
  `!games/sonic4/data/editor/ojz/act1/section_*.{tiles,coll,collattr,collattrb}.bin` — under
  the comment *"the OJZ generated level tree + collision tables ship as COMMITTED artifacts
  (the sound-migration model — reproducible-by-tracking) … A fresh checkout builds from these
  tracked bytes with no seed step."*
- `tools/regenerate-level.sh` ends with *"review `git status games/sonic4/data` before
  committing"* and *"COMMIT `DONOR_PROVENANCE.json` WITH the tree."*

The generators read two **out-of-repo donor projects** (`sonic_hack`, `skdisasm`) that exist
only on an authoring machine, so the build can never run them. Tracking the bytes is the whole
design. These files are pile 2.

### So why were they never committed?

Three compounding reasons, all evidenced:

1. **A standing instruction to not touch them, repeated in ~15 documents.**
   `docs/superpowers/2026-08-16-next-session-handoff.md:212` — *"`git add` exact paths only.
   `games/sonic4/data/editor/**` belongs to an auto-commit daemon."*
   `2026-08-14-next-session-handoff.md:16` — *"Working tree has only the pre-existing
   editor-JSON churn (auto-commit daemon territory) … **Not ours.**"*
   `2026-08-16-overnight-work-order.md:58` — *"auto-commit daemon; never stage, revert or
   touch it."* Session after session saw the dirt, correctly obeyed, and moved on.

2. **The daemon is not running and has not landed anything in ten days.** No systemd user unit
   matches (only `aeon-effects-gates.timer` and `sigil-source-gates.timer` exist), and no
   matching process is alive. The last commit touching `data/editor/ojz/act1` is `a447e0fd`
   (**2026-08-12**); `ojz_bglib.json` has not been committed since the June 28 directory move.
   The 08-19/08-20 edits have simply never been picked up.

3. **The blast radius outgrew the daemon's remit and nobody owned the rest.** The daemon (when
   it ran) watched `data/editor/` only. The 08-20 re-bake also rewrote `data/collision/**` and
   `data/generated/**`, which were **never** daemon territory — the last time they changed, a
   human committed them by hand as `14ac489a`. But "editor churn, not ours" got applied to the
   whole `games/sonic4/data` blob, so the derived half was orphaned too.

**The 2026-08-12 precedent is the template to copy.** `a447e0fd` +`14ac489a`, both stamped
`15:27:25`, are the same edit shape committed as a **matched pair**:
`a447e0fd data(ojz): user-authored solid test walls in section 0 (shape 255 flat)` (editor
files) and `14ac489a data(ojz): re-baked level tree + collision for the wall edit` (collision +
generated). That is exactly the split proposed in §4.

---

## 2. The strays

### `games/sonic4/data/editor/ojz/act1/export/` — 3 files — **PILE 1 (gitignore)**

`act_descriptor.asm`, `entity_data.asm`, `vram_bases.asm`, mtime 2026-08-12 19:17.

**These three exact files were deliberately deleted on 2026-08-01 by `46c2e0f0` "Parcel J:
delete the parked ojz editor exports (#25/#26/#27)", on an explicit owner pre-ruling
("Volence pre-ruled DELETE"), with an unwired-proof in the commit body:** no build file, sigil
test or tool reads the path, and all 47 `ojz_*` labels they define are referenced only inside
the export dir. Aurora's editor re-emitted them eleven days later on a save. They are untracked
because they were deleted on purpose and never re-added.

Two further confirmations they are dead output, not work:
- They are a **legacy `.asm` export**, and `docs/DEFERRED_WORK.md` (ruling 2026-08-20) states
  *"Their June `.asm` route is dead (asl left the pipeline)"*.
- `act_descriptor.asm` contains outright broken output —
  `dc.l games/sonic4/data/parallax/ojz_default.asm ; act_parallax_config`, a **file path
  emitted where a symbol belongs**. Nothing has ever assembled this.
- It also still references the *old* `ojz_BG_deep_forest_v16_…` layout, i.e. it predates the
  08-19 BG change and was never refreshed.

Ignoring the directory honours the existing DELETE ruling without removing anything from disk,
and it is **inert with respect to build behaviour**: `tools/level_staleness.py` already excludes
the directory by name (`SKIP_DIR_NAMES = {"export"}`, covered by `test_export_dir_is_excluded`),
so it is not a staleness input either way.

### `games/sonic4/data/sprites/object-bindings.json` — **PILE 2 (keep), low confidence, defaulted to keep**

2 bytes, content `{}`. Untracked since at least 2026-08-13.

Evidence both ways. **For keeping:** its siblings in the same export root *are* tracked
(`games/sonic4/data/sprites/index.json`, `pitcher_plant/sprite.json`) — a tracked sibling with
an untracked twin. And `docs/DEFERRED_WORK.md:137` names it directly: *"NOTE:
`object-bindings.json` is currently UNTRACKED in this repo — the consumer parcel decides
tracked-vs-generated as part of the contract, **don't let it linger untracked**."*
**Against:** it is empty, and the same deferred note reserves the tracked-vs-generated
decision for the (unbuilt) Aurora sprite-export consumer parcel.

**Provenance is only partly determined** — Aurora's exporter writes it, but why it was left out
when `index.json` was added is not recoverable from this repo. Per the keep-by-default rule it
goes in pile 2, as its **own commit** so it is trivially revertible if the consumer parcel rules
it generated.

### `s4.state0`, `s4.debug.state0`, `s4.debug.state1` — **PILE 3 (junk)**

Inspected as bytes only, never loaded into an emulator. Magic `ONSS` (Oracle save-state),
~870-886 KB each, mtimes 2026-08-17. Ephemeral debugging save-states pinned to one ROM build,
written beside the ROM at the repo root. Untracked because no rule covered them and nobody
wanted them. Matched by **no** existing ignore rule (`check-ignore` rc=1), which is why they
have shown as noise for five days. Ignore them; leave the files on disk for the owner to delete
whenever.

---

## 3. The `.gitignore` additions (pile 1 + pile 3)

Added after the `chunks_tiles.bin` negation block:

```gitignore
games/sonic4/data/editor/ojz/act1/export/
/*.state*
```

(each with the full rationale in comments — see the diff on this branch).

**Over-match check.** `git check-ignore -v` run over **all 1118 tracked files**: rc=1, no
output — **zero tracked files match any ignore rule**. Targeted checks confirm the new rules
match the six intended paths, and that every must-stay-tracked path is still fine, including
`games/sonic4/data/replays/*.bin` (the `/*.state*` rule is root-anchored and cannot reach it).
Note when re-running this by hand: `check-ignore -v` exits 0 for **negation** rules too — read
the `!` prefix on the reported pattern, do not trust the exit code alone.

---

## 4. Staging plan for the main tree

Run from `/home/volence/sonic_hacks/aeon`. Exact paths only, no `-A`, no globs — other
sessions' work is in this tree.

> **Commits 1 and 2 must land together.** The collision tables are *interned* against the strip
> indices in the generated tree; committing one without the other breaks that pairing, and
> `verify_level_bin.py` is the only thing that checks it.

**Commit 1 — the authoring (mirrors `a447e0fd`)**

```bash
git add games/sonic4/data/editor/ojz_bglib.json \
        games/sonic4/data/editor/ojz/act1/section_0.meta.json \
        games/sonic4/data/editor/ojz/act1/section_0.objects.json \
        games/sonic4/data/editor/ojz/act1/section_0.tiles.bin \
        games/sonic4/data/editor/ojz/act1/section_0.collattr.bin \
        games/sonic4/data/editor/ojz/act1/section_0.collattrb.bin
git show --stat --cached      # expect exactly 6 files
git commit -m "data(ojz): section 0 paint + collision edit, and the in-game forest BG binding

Two Aurora saves that were never landed. 2026-08-19: adds BG layout
'ingame-forest-v15-1786630615596' (In-game forest, engine v15) to ojz_bglib.json,
repoints section 0's bgLayoutRef to it from deep-forest-v16-trunks-over-wall, and
nudges the section-0 solid object 803,208 -> 808,210. 2026-08-20: paints a
contiguous region of section 0 - tiles.bin, collattr.bin and collattrb.bin all
differ across the identical byte range 16609..24351."
```

**Commit 2 — the bake (mirrors `14ac489a`)**

```bash
git add games/sonic4/data/collision/angles.bin \
        games/sonic4/data/collision/heightmaps.bin \
        games/sonic4/data/collision/heightmaps_rot.bin \
        games/sonic4/data/collision/solidity.bin \
        games/sonic4/data/generated/ojz/act1/DONOR_PROVENANCE.json \
        games/sonic4/data/generated/ojz/act1/act_pool_page4.bin \
        games/sonic4/data/generated/ojz/act1/act_pool_page4.zx0 \
        games/sonic4/data/generated/ojz/act1/act_pool_page5.bin \
        games/sonic4/data/generated/ojz/act1/act_pool_page5.zx0 \
        games/sonic4/data/generated/ojz/act1/act_pool_page6.bin \
        games/sonic4/data/generated/ojz/act1/act_pool_page6.zx0 \
        games/sonic4/data/generated/ojz/act1/act_pool_page7.bin \
        games/sonic4/data/generated/ojz/act1/act_pool_page7.zx0 \
        games/sonic4/data/generated/ojz/act1/act_pool_page8.bin \
        games/sonic4/data/generated/ojz/act1/act_pool_page8.zx0 \
        games/sonic4/data/generated/ojz/act1/entity_data.emp \
        games/sonic4/data/generated/ojz/act1/sec0_blocks.bin \
        games/sonic4/data/generated/ojz/act1/sec0_local_map.bin \
        games/sonic4/data/generated/ojz/act1/sec0_strips_a.bin \
        games/sonic4/data/generated/ojz/act1/sec0_strips_source.bin \
        games/sonic4/data/generated/ojz/act1/sec1_blocks.bin \
        games/sonic4/data/generated/ojz/act1/sec1_local_map.bin \
        games/sonic4/data/generated/ojz/act1/sec1_strips_a.bin \
        games/sonic4/data/generated/ojz/act1/sec2_local_map.bin \
        games/sonic4/data/generated/ojz/act1/sec3_local_map.bin \
        games/sonic4/data/generated/ojz/act1/sec4_local_map.bin \
        games/sonic4/data/generated/ojz/act1/sec5_local_map.bin \
        games/sonic4/data/generated/ojz/act1/sec6_local_map.bin \
        games/sonic4/data/generated/ojz/act1/sec7_blocks.bin \
        games/sonic4/data/generated/ojz/act1/sec7_local_map.bin \
        games/sonic4/data/generated/ojz/act1/sec7_strips_a.bin \
        games/sonic4/data/generated/ojz/act1/sec8_local_map.bin
git show --stat --cached      # expect exactly 32 files
git commit -m "data(ojz): re-baked level tree + collision for the section 0 edit

The 2026-08-20 13:45 re-bake of the preceding commit's editor edits, never landed.
Reproduced byte-identically from those inputs by tools/regenerate-level.sh
(78/78 files identical; only DONOR_PROVENANCE.json differs, and it stamps the run
- donor SHAs, aeon HEAD, dirty counts - not the content). verify_level_bin.py OK.
Collision deltas are confined to interned shape slots 14-20."
```

**Commit 3 — the ignore rules + this note.** Already committed on
`parcel/dirty-tree-triage`; cherry-pick or merge it.

**Commit 4 (optional) — the sprite-export stray**

```bash
git add games/sonic4/data/sprites/object-bindings.json
git show --stat --cached      # expect exactly 1 file
git commit -m "data(sprites): track the empty object-bindings.json export root

Untracked twin of the tracked index.json / pitcher_plant/sprite.json. Content is
'{}'. DEFERRED_WORK's Aurora sprite-export consumer parcel still owns the
tracked-vs-generated ruling; tracking it now only stops it lingering, per that
note's own instruction. Own commit so it is trivially revertible."
```

### After landing — flag for the owner

**Commits 1+2 change ROM bytes.** The level data is embedded in `s4.bin`, so landing them moves
the ROM and very likely moves sigil pins. **This triage deliberately ran no build** (nothing
here needed one). Before merging to `master`, run the standing byte-changing-parcel ritual:
canonical `./build.sh` (both shapes), then repin → refreeze. That is an owner call, not
something this parcel should have done blind.

---

## 5. Gaps, corrections, and things worth a second look

**Could not determine (defaulted to KEEP):**
- `object-bindings.json` — *why* it was left untracked when `index.json` was added is not
  recoverable. See §2.
- Which *person or process* invoked the 2026-08-20 13:45:39 re-bake. `FAST=1 ./build.sh`
  auto-re-bakes on a stale editor tree, and `regenerate-level.sh` can be run by hand; the
  mtimes cannot distinguish them. It does not affect the disposition — the output is proven
  correct either way.

**A separate gap found while triaging, NOT part of the 43 and NOT acted on:**
`games/sonic4/data/sprites/pitcher_plant/art.bin` (2944 B) and `mappings.bin` (240 B) have been
on disk since 2026-06-17 and are **silently swallowed by the blanket `*.bin`** with no
negation, so they never appear in `git status` at all. Their sibling `sprite.json` *is*
tracked. That is real Aurora export data invisible to the repo. `.gitignore`'s own comment
warns about exactly this class (*"SOURCE .bin data must be tracked … Negate explicitly rather
than force-add"*), and it is how `ojz_tiles.bin` was lost before (tools lens sweep D2). Left
alone here because the DEFERRED_WORK sprite-consumer parcel owns that format contract — but
**the owner should know these two files exist and are not backed up by git.**

**Corrections to the brief that commissioned this triage:**
- The rough breakdown was accurate but omitted `games/sonic4/data/editor/ojz_bglib.json`,
  which is under `data/editor/` but not under `ojz/act1/` — it is the 6th modified editor file.
- The brief expected the three `*.state*` files to be "the obvious members" of the junk pile
  and they are, but the `export/` directory is better handled as pile 1 (ignore) than pile 3,
  because there is an existing owner DELETE ruling to honour rather than a judgement to make.
- Pile 1 turned out to be **much smaller than the shape of the tree suggests**. The obvious
  reading — "`data/generated/` is generated, therefore ignore it" — is wrong here and the repo
  has already argued why in `.gitignore` and in `regenerate-level.sh`.

**Standing-instruction defect worth fixing separately:** the ~15 handoff documents that say
`games/sonic4/data/editor/**` is daemon-owned and must never be staged are now **actively
harmful**, because the daemon is gone. Whichever way that is resolved (restart the daemon, or
strike the instruction), leaving both the dead daemon and the live instruction in place will
strand the next editing session's work exactly the same way.

---

## 6. Safety confirmation

**Nothing was written to the main working tree at `/home/volence/sonic_hacks/aeon`.** No `git
add`, `checkout`, `stash`, `clean`, `commit`, no edits, no deletions. Reads only (`stat`,
`cat`, `diff`, `cp` *from* it). Both re-bakes ran inside the agent worktree with an explicit
`cd` guard. Git redirection into the main tree was refused by worktree isolation throughout,
which is also an independent guarantee.

**Drift.** The reconstruction was re-run at the end of the session. **All 43 status entries (45
files, once the `export/` directory line is expanded) are still present, with unchanged sizes
and unchanged mtimes; the modified set is still exactly 38.** Zero drift in the triaged set.

The main tree is *not* idle, though: another session was actively working in it throughout,
touching `games/sonic4/vram.toml`, `tools/vram_map.py`, `games/{sonic4,demo}/config/constants.emp`
and `docs/generated/vram-map-*.md` (the VRAM-linker parcel), plus `tools/png_to_bg_override.py`
and `tools/test_bg_tile_budget.py`. None of those files' *contents* diverged from `master`
during the session and none overlap the 43. The only new file on disk was a `__pycache__`
`.pyc` (ignored). **This is exactly why the staging plan enumerates every path and uses no
globs** — a `git add games/sonic4/` at the wrong moment would sweep that session's work in.

**No emulator was touched.** The three save-states were read as bytes (`xxd` of the first 64)
and never loaded.
