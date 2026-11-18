# C3b-3 probe builds: the forced-race ROMs for the runtime TAG (2026-09-12 UTC)

> **Correction (2026-11-17, review before landing on master).** (1) This note says it is builds only, on a throwaway branch that is never merged. The probes were measured afterwards and the result is in `docs/superpowers/notes/2026-09-12-c3b3-runtime.md`. The C3b-3 RUNTIME TAG is CLOSED (`docs/DEFERRED_WORK.md`), and that comparison used unfixed vs fixed-control. The probe branches are deleted. The ROMs survive only under `.aeon-probes/c3b3/`, outside the repo. (2) In "Where the brief or the note disagrees", item 1, "so 20 bytes of earlier code changed" is wrong. The fix's 14 bytes sit after `PageIn_Process`'s entry and cannot move it: fixed-control has the entry at the same `$90F6` as unfixed. The 6-byte drop in the origin/master probe is a net 6-byte shrink of code ahead of `Level_LoadArt` (`$903E` to `$9038` in the two listings). The conclusion that this pair is not a clean control still stands.

A RECORD (`docs/superpowers/**`), on the THROWAWAY branch `probe/c3b3-race-fixed`. None of
these branches is ever merged; the controller deletes them after measuring. Serves the
`C3b-3 RUNTIME TAG` in `docs/DEFERRED_WORK.md` and section 6 of
`docs/superpowers/notes/2026-09-11-c3b3-pagein.md`. No emulator was used here: these are
builds only, and nothing below is a runtime measurement.

## The spin, and where it sits

The same five lines (two comment, one label, two instructions) in both probes, in
`engine/level/page_in.emp`, `PageIn_Process` `.land`, immediately after `bcs .land_full`:

```
    .probe_spin:
        tst.b   VBlank_Flag
        beq     .probe_spin
```

It mirrors `VSync_Wait`'s `.wait` test (`tst.b VBlank_Flag` / `beq .wait`) and, unlike `.wait`,
never clears the flag, so `VSync_Wait`'s own `.wait` still sees it set and falls through.
Emitted as `4a38 8000 67fa` (`tst.b ($8000).w`, `beq.s` back 6 bytes) in both ROMs, read out
of the ROM bytes, with `50f8 ba4e` (`st.b PageIn_Staging_Busy`) as the very next word.

**Unfixed (pre-fix tree).** Between `bcs .land_full` and `st.b PageIn_Staging_Busy`, exactly
as the TAG says.

**Fixed.** The fix did NOT close the window by construction: it keeps the order (enqueue, then
raise) and recovers AFTER the raise with a re-test of VInt_Level's release predicate. So
"between the enqueue and the flag" still exists in the fixed order, and it is the same point:
between `bcs .land_full` and `st.b PageIn_Staging_Busy`, before the raise and the re-test
(the note's section 6 says "the same three lines at the same place (before the raise and
re-test)"). The spin sits ahead of the fix's long comment block; that block emits no bytes.

**Why that point forces the race.** `VSync_Wait` clears `VBlank_Flag` and sets
`VBlank_Ready = 1` in its `ints_off` bracket before it calls `PageIn_Process`
(`engine/system/vblank.emp`, `VSync_Wait`), and `PageIn_Process`'s only caller is
`VSync_Wait` (grep over `engine` and `games` `.emp`). So on entry to the spin the flag is 0 and
the next IRQ6 is `VInt_Level`: it drains the Important queue (the landing was enqueued
just above, under `$2700`, by `PageIn_EnqueueLanding`), runs the release test while
`PageIn_Staging_Busy` still reads 0 (skips the release), sets `VBlank_Flag`, and the spin
exits. That is the section-2 interleaving of the pagein note, with the VBlank placed at the
END of its ~450-cycle window instead of by chance. In the fixed probe the raise is then
followed by the re-test, which should see slot == base and clear.

**What the spin does not force.** If a VBlank already ran earlier in the same
`PageIn_Process` call (the resume-setup straddle, note section 2 "Sub-case"), `VBlank_Flag` is
already 1 and `VBlank_Ready` is 0 at `.land`: the spin falls straight through and no
`VInt_Level` lands in the window for that page. The forced VBlank also only empties the queue
when the landing fits `DMA_Budget_Remaining` (at init, `DMA_BUDGET_BLANKED_INIT`); where it
does not, the queue stays non-empty and there is nothing to violate. Both are the note's own
caveats, restated, not re-derived.

**Why the spin does not change what is measured.** It only waits; it writes nothing. The two
cells the invariant reads (`PageIn_Staging_Busy`, `DMA_Important_Slot`) and the queue base are
untouched by it, and the handler that ends the spin (`VInt_Level`) is the one the invariant is
about. The cost is that every ZX0 landing now waits for the VBlank that `VSync_Wait`'s `.wait`
would have waited for anyway; the landing's `PageCache_Publish` runs after that VBlank
instead of before it. `.land` is main-loop code below IPL 6 (`VSync_Wait`'s stated
precondition), so the spin cannot deadlock on a masked IRQ6. The raw-form arm
(`PageIn_EnqueueLanding` from `.raw`) never touches `PageIn_Staging_Busy` and is not probed.

## Build environment (both probes)

- `SIGIL_BUILD=/home/volence/sonic_hacks/sigil/target/release/sigil`,
  md5 `49ecc532e0b133ab0eab9447e071805c`; the build printed `Assembler: sigil af35fa561663
  (clean at capture, no uncommitted changes)`.
- `SIGIL_EMIT` md5 `8d80a57809979d43fe8d7c3a0a9ded13`; `AEON_SKDISASM_DIR=/home/volence/sonic_hacks/skdisasm`.
- One `DEBUG=1 ./build.sh` per probe, detached, with a per-run `PYTHONPYCACHEPREFIX`.

## Probe 1: unfixed

- Branch `probe/c3b3-race-unfixed`, tip `302c447168085d331a62bc31d3d328d41b1a95d8`.
- Base `3492ce3a442af8aa54e031d1a0d01a1880933f9f`, the FIRST parent of merge `b29a53ae`
  (`git log -1 b29a53ae`: parents `3492ce3a` and `01f8444c`). At the base, `.land` reads
  `bcs .land_full` then `st.b PageIn_Staging_Busy`, and `landing_queued` does not occur in
  `engine/level/page_in.emp`.
- Build: run 2026-09-12T00:20:51Z to 00:24:03Z, `REAL_EXIT=0`, `finished=0`.
  `built: sonic4 debug native ROM, crc=22aee8d3 len=847387`. Lanes in the log:
  `2428 passed, 2 skipped, 14 deselected, 5 warnings, 112 subtests passed` (pre-build) and
  `6 passed, 8 skipped, 2430 deselected` (post-sigil).
- Stable copy: `/home/volence/sonic_hacks/.aeon-probes/c3b3/unfixed/s4.debug.{bin,lst}`
  (`cmp`-identical to the build output at copy time).
  - `cksum`: `3064938474 847387`
  - `md5sum`: `6e9b4681d90dc02a9584d2dd91b2a6c6`

## Probe 2: fixed

- Branch `probe/c3b3-race-fixed`, probe commit `4ddf3ce9a5f61d9ca2306f88ea7f72b010f8182d`
  (this note sits in a later commit on the same branch; it changes no source byte).
- Base `origin/master` = `35f54923138a7433749d5db7d5a1b270681d5607`
  (`git merge-base --is-ancestor b29a53ae origin/master` true; `.landing_queued` present).
- Build: run 2026-09-12T00:16:39Z to 00:20:07Z, `REAL_EXIT=0`, `finished=0`.
  `built: sonic4 debug native ROM, crc=569eff6d len=847409`. Lanes in the log:
  `2442 passed, 2 skipped, 14 deselected, 5 warnings, 112 subtests passed` (pre-build) and
  `6 passed, 8 skipped, 2444 deselected` (post-sigil).
- Stable copy: `/home/volence/sonic_hacks/.aeon-probes/c3b3/fixed/s4.debug.{bin,lst}`
  (`cmp`-identical to the build output at copy time).
  - `cksum`: `3444803359 847409`
  - `md5sum`: `373f334f5b568f0af357243b03e92e97`

## Addresses, read from each probe's own `.lst`

Read by script from the listing's symbol table (` NAME : HEX C |` rows), then checked against
the ROM bytes at each code address. Use the listing of the ROM under test, not this table.

| symbol | unfixed | fixed |
|---|---|---|
| `PageIn_Process` entry | `$0090F6` | `$0090F0` |
| `PageIn_Process.land` | `$009362` | `$00935C` |
| spin loop `PageIn_Process.probe_spin` | `$009372` | `$00936C` |
| `st.b PageIn_Staging_Busy` (spin + 6) | `$009378` | `$009372` |
| `PageIn_Process.landing_queued` | (absent) | `$009384` |
| `PageIn_Process.land_full` | `$009388` | `$009390` |
| `Level_LoadArt` `clr.b PageIn_Bulk_Drain` | `$0090C2` | `$0090BC` |
| RAM `PageIn_Staging_Busy` (u8) | `$FFFFBA4E` | `$FFFFBA4E` |
| RAM `DMA_Important_Slot` (u16) | `$FFFF820C` | `$FFFF820C` |
| RAM `DMA_Important` (queue base, an address) | `$FFFF80BA` | `$FFFF80BA` |
| RAM `Frame_Counter` (u16) | `$FFFF8002` | `$FFFF8002` |
| RAM `VBlank_Flag` (u8) | `$FFFF8000` | `$FFFF8000` |
| RAM `PageIn_Bulk_Drain` (u8) | `$FFFFBA79` | `$FFFFBA79` |

**The `clr.b` address is derived, not a listing row.** The sigil `.lst` carries labels and a
symbol table, not instruction lines, so no row names the `clr.b`. It is the instruction
immediately before `$engine.load_art$Level_LoadArt$bg` in the source (`load_art.emp`:
`clr.b PageIn_Bulk_Drain` then `.bg:`), and `clr.b abs.w` is 4 bytes, so its address is
`.bg - 4`: unfixed `$0090C6 - 4`, fixed `$0090C0 - 4`. The ROM holds `4238 ba79`
(`clr.b ($BA79).w`, `PageIn_Bulk_Drain = $FFFFBA79`) at that address in both ROMs.

Bytes after the raise, as a cross-check of which tree each ROM is: fixed `3038 820c 0c40 80ba`
(`move.w DMA_Important_Slot, d0` / `cmpi.w #DMA_Important, d0`, the fix's re-test); unfixed
`3038 ba76 1238 ba78` (straight into the `PageCache_Publish` argument loads).

## Where the brief or the note disagrees with the tree

1. **The two required probes are not a clean control.** The pagein note's section 6
   "Control" says to build the two probes "from one tree that differs ONLY in the fix".
   The brief cuts the fixed probe from `origin/master`, which is 49 commits past `b29a53ae`
   and touches `engine/sound/*`, `engine/system/buffers.emp`, `engine/system/constants.emp`,
   `games/sonic4/player/player_instashield.emp`, `games/sonic4/objects/ring_sparkle.emp` and
   others. Visible in the table: `PageIn_Process` sits 6 bytes LOWER in the fixed ROM
   although the fix adds 14 bytes after it, so 20 bytes of earlier code changed between the
   bases. The invariant check (zero violations in the fixed probe) does not depend on this.
   The `Frame_Counter` discriminator (unfixed about one frame later per ZX0-form page) does,
   because anything else that moved init timing moves that number. A third probe cut from
   `b29a53ae` itself (tree = `3492ce3a` + the fix only: `git diff --stat 3492ce3a b29a53ae`
   is `engine/level/page_in.emp`, a `vblank.emp` comment, and two docs) is recorded below
   as the clean control.
2. **The listing has no instruction rows** (see above), so the `clr.b` address had to be
   derived and byte-checked; it is not "read from the listing" in the literal sense.
3. **The date.** `date -u +%F` was 2026-09-12 at build time (local 2026-09-11), hence this
   file's name.

## Probe 3 (beyond the brief): fixed-control, the fix-only pair for the frame discriminator

Built because of disagreement 1. Use unfixed vs fixed-control for the `Frame_Counter`
comparison; either fixed ROM serves the invariant check.

- Branch `probe/c3b3-race-fixed-control`, tip `45496409542d98da8d21361649ab8d5277860a12`.
- Base `b29a53ae362976a1dc187e35ca397a6de7b6c60f` (the fix merge itself). `git diff --stat
  302c4471 45496409` (unfixed probe tip vs this tip) is exactly
  `docs/ENGINE_ARCHITECTURE.md`, `docs/superpowers/notes/2026-09-11-c3b3-pagein.md`,
  `engine/level/page_in.emp`, `engine/system/vblank.emp`: the fix commit's four files, so the
  two probes differ ONLY in the fix. The spin diff is the same five lines at the same place as
  probe 2.
- Build: run 2026-09-12T00:26:49Z to 00:30:33Z, `REAL_EXIT=0`, `finished=0`.
  `built: sonic4 debug native ROM, crc=e7060c57 len=847409`. Lanes:
  `2428 passed, 2 skipped, 14 deselected, 5 warnings, 112 subtests passed` (pre-build) and
  `6 passed, 8 skipped, 2430 deselected` (post-sigil).
- Stable copy: `/home/volence/sonic_hacks/.aeon-probes/c3b3/fixed-control/s4.debug.{bin,lst}`
  (`cmp`-identical at copy time).
  - `cksum`: `4118751042 847409`
  - `md5sum`: `ea3dcaeed5f8922b6f2fb7b939a519a5`
- Addresses from its own listing, byte-checked as above: `PageIn_Process` `$0090F6`,
  `.land` `$009362`, spin `$009372` (`4a38 8000 67fa`), `st.b PageIn_Staging_Busy` `$009378`
  followed by the re-test `3038 820c 0c40 80ba`, `.landing_queued` `$00938A`, `.land_full`
  `$009396`, `Level_LoadArt` `clr.b PageIn_Bulk_Drain` `$0090C2` (`4238 ba79`). RAM identical
  to the table above (`PageIn_Staging_Busy $FFFFBA4E`, `DMA_Important_Slot $FFFF820C`,
  `DMA_Important $FFFF80BA`, `Frame_Counter $FFFF8002`, `VBlank_Flag $FFFF8000`).
- Layout vs the unfixed probe: `PageIn_Process`, `.land`, the spin and the `clr.b` sit at the
  SAME addresses; `PageIn_BankRegs` moves by exactly +14 (`$9434` to `$9442`). `cmp -l` of the
  two ROMs: the first differences are the header checksum word (`$18E`), the header ROM-end
  field (`$1A7`), and `$383`, the low byte of the `jsr` operand at `$380` (`jsr $0000A71C`
  at `$37E` becomes `jsr $0000A72A`, +14, an absolute call
  from `EntryPoint` into the shifted span). The rest (56518 byte positions in total, plus the
  22-byte longer file) was not individually classified.
