# Audit briefing for the aeon lane — 2026-09-09 evening

**From:** the owner's audit session (aeon-c1, then aeon-3e after a reboot), at the owner's request:
*"Fix the cards. Answer any you can. Send info on any cleanups or things the current running agents
should do from your audit."* Every claim below cites where it was read; nothing here was verified on
an emulator. Reviewer material comes from four read-only reviewers who sampled ~50 code commits
across the suite, calibrated by the audit session reading three aeon diffs itself.

## 1. Owner cards — what changed in `docs/decisions.jsonl` and what the lane owes

Recorded as `answered` rows with `by: "hub"` (the Dominion contract allows only owner | hub | lane)
and the owner's delegation quoted in `said`. **Drop each from `blockedOnOwner` in the next board
write; the owner overturns any of them with one word.**

| card | chose | note |
|---|---|---|
| LS-13 | `document` | the hub already ruled it 2026-09-06; comments landed |
| REGIONS-V1-WORTH-IT | `build` | closure pass landed at `ff9cb978` (design doc §10); parcel 1 may start |
| WATERLINE-OFF-READING | `gone` | already shipped at `a422e7bc`, reversible |
| SPRING-PAL-IDX9 | — | **new ledger row written**; the card existed only on the board so the console could not render it. Stays owner-level (eye call) |
| VRAM-FOR-OBJECTS | — | untouched; genuinely owner-level |

## 2. Regions v1 — read before starting parcel 1

`docs/superpowers/designs/2026-09-09-regions-v1-design.md` §10 (landed `ff9cb978`): Q1/Q4/Q5/Q6/Q7
resolved; the crossing gate is green on master; **two findings the plan did not have**: the T1 gate
itself reads `Parallax_Prev_Sec_X/Y` (which step 3 deletes) so its detector must be repointed and
inverted in step 3's commit, and `boot_override_gate` derives its expectation from the `Boot_At`
section rather than the clamped camera centre, so T2 is a rewrite. Net cost revises to +152 emitted.

## 3. Cleanups and defects found, in priority order

1. **Palette never reaches the ROM — aeon's half is unbooked.** `tools/ojz_strip_gen.py:2136-2138`
   `shutil.copy`s the donor `art/palettes/OJZ.bin` over `ojz_palette.bin` on every bake. Aurora booked
   its half (PALETTE-NEVER-REACHES-ROM); aeon has no row in lane-status, lane-log or DEFERRED_WORK.
   A chip was left on the owner's console; if it is not taken, book and fix it here.
2. **32 orphaned generated files in the main tree.** `games/sonic4/data/sound/sfx/sfx_*.asm` and
   `*_patches.asm` (untracked since 2026-09-08 00:46) are `tools/sfx_transcode.py` output in the format
   master deleted at `4b89ae24`; master tracks only the `.bin` twins. Delete or gitignore them.
3. **Owner's editor edits uncommitted on master** (`games/sonic4/data/editor/ojz/act1/section_0.*`,
   `chunklinks.json`, the effects presets). The auto-commit daemon is dead. NOT committed by the audit
   because `section_0.tiles.bin` may be the F09 tile rebuild awaiting the owner's d-33 answer; settle
   which it is and commit or revert deliberately.
4. **A comment claims a measurement the commit says was derived.** `9930f46e`,
   `engine/objects/entity_window.emp:985`: "Measured off the shipped release bytes: this gate is 138c"
   while the commit body says "DERIVED STATICALLY... NOT measured." Fix the comment.
5. **Two text lints with no fixture that proves they can go red:** the parallax publish-order lint
   from `68f34815` and the Timer-A defer lint from `b2fd9cdc`. A regex drift leaves them green forever.
   Plant a fixture for each.
6. **`PLAYERV_SPEND` is 29 of a 30-byte window** (`games/sonic4/player/player_common.emp:251`) after
   `fe8422d9`. The next ability field forces a layout change that moves every `*_cut.json` fixture.
   Book the cliff before someone hits it.
7. **`SOLID_TOUCH_W` fixes X only** (`a7f088af`, `constants.emp:158`); a curled player still contacts
   on a different vertical face. Argued and booked; watch for the next vertical "passes through" report.
8. **`.mcp.json` `exodus` entry** points at `oracle/linux-port/mcp/oracle-mcp`, which does not exist;
   every session starts with a failed MCP connection. Chip left; otherwise remove the entry.
9. **`docs/DEFERRED_WORK.md` is 31,898 lines / 2.5 MB.** Archive closed sections the way the bugs list
   was archived on 2026-09-09.

## 4. Quality verdict for the record

Sampled grades (11 code commits): correctness A-, conventions A, tests B, cleanliness A, message
honesty B+. Zero hand-sized branches, zero `mulu`/`divu`, zero TODOs added since 09-06. Decisions:
the discriminating experiment was run in every sampled case; the WATERLINE inference was correctly
surfaced as the lane's own call. Suite-wide, 27% of aeon's commits since 09-06 touch code; the rest is
boards, logs and audits.
