# Lens bin C: owner decision cards, DRAFTED (not filed)

Drafted 2026-09-11 on `cards/lens-owner-bin-0911`, cut from `origin/master` 6d4b5656. Source list:
`docs/superpowers/notes/2026-09-11-lens-open-sift.md`, "Bin C" (five ids). Nothing here is appended
to `docs/decisions.jsonl`: the controller files. Every card below was dry-run with
`python3 tools/decisions_append.py --check-only --now <file>` against this branch's ledger, and the
JSON printed under each card is the exact file that was dry-run (filled into this note by a script
from those files, so no hand re-typing sits between the check and the text).

## Rulings first

1. **CTRL-3 and V-8 are ONE question, and get ONE card (id `CTRL-3`).** V-8's own enforcement
   options are "a merge hook, or CI per CTRL-3" (sift, Bin C). Every answer to one answers the
   other: keep the ritual (both stay open by choice), a landing command that refuses the merge
   (closes V-8, answers CTRL-3 as "local"), hosted CI (answers CTRL-3, closes V-8 after the fact).
   Two cards would let him answer one and leave the other reading as still owed. When he answers,
   BOTH ledger rows move.
2. **CHAR-10 gets an AEON card.** The brief's premise that "the recorder and the fixture format
   belong to the ORACLE lane" is half wrong. The fixture FORMAT (`ARP0`), its packer
   (`tools/replay_pack.py`) and the in-ROM recorder (`engine/system/replay.emp`, DEBUG-only
   `INPUT_RECORD`) are aeon's. Oracle owns the headless runner and the restamp tool
   (`crates/oracle-replay`), which refuses a non-zero `pad` or `reserved` header byte, so any
   character byte needs a matching oracle change. Oracle's ledger at `origin/main` adcf2395 has no
   card on this (its `origin/master` is a stale branch from 2026-06-24). The firsthand measurement
   (the single writer of `Character_ID` and its playback gate) is aeon's, so under contract rule 10
   aeon holds the one card and oracle references it.
3. **EFX-2 and B1-6 get one card each.** No merge.
4. **Hub pre-emption, checked by hand** because the tool's own check cannot run from a worktree
   (it resolves `../empyrean` relative to the cwd; every dry-run below prints `COULD NOT CHECK`).
   Read at empyrean `origin/main`: `docs/OVERSEER.md` names none of the five ids; `docs/OVERSEER-LOG.md`
   has no 2026-09-10/11 line on CI, hooks, landing commands, fades, lints, replay or characters.
   One OLDER hub ruling bears on card 1 and is quoted in its detail: 2026-09-05T22:48:31Z, pre-push
   hook enforcement "RULED available not mandated ... each lane may install one running its own
   landing command". So card 1's recommended option needs no hub ruling. **At file time, re-run the
   dry-run from the main checkout** (where `../empyrean` resolves) so the tool's own check runs.

## What in the brief was wrong or looser than the tree

- "all ten `preset(...)` sites use 0" (EFX-2): there are **nine** real call sites, all in
  `games/sonic4/data/effects/ojz_effects.emp`. The tenth grep hit is a comment in
  `games/sonic4/data/generated/ojz/act1/effects_scenes.emp` (a template line). The ledger row and the
  sift carry the same miscount.
- More important for EFX-2: **all nine presets pass the same palette** (`OJZ_Palette`). Setting a
  non-zero transition today would fade a palette into itself and show nothing. "Ship a cross-fade"
  therefore also needs a second palette, which is content and his eye call. The card says so.
- "The recorder and the fixture format belong to the ORACLE lane" (CHAR-10): see ruling 2.
- "LS-2, LS-14 set a precedent against heuristic text lints" (B1-6): looser than the rows. LS-2
  declined ONE lint for three stated reasons specific to over-declared clobbers (deliberate in the
  codebase, not a correctness class, byte-moving pressure on sigil). LS-14 retired s4lint because its
  subject had collapsed to one 8-line file, not because it was heuristic. The card cites them in
  those terms. The stronger argument against a text lint is LS-8's own finding: some of the
  dangerous copies contain no literal at all.
- CHAR-10's live evidence (the red spring's colour under Knuckles) would **not** have been caught by
  a Knuckles fixture: the replay net hashes the player's state and is pixel-blind. The card states
  this in the recommended option's own text so it cannot be sold on the spring.

---

## Card 1: `CTRL-3` (covers CTRL-3 and V-8)

**Evidence.**
- **The two ledger rows.** CTRL-3's latest line (09-09T10:52) says aeon has no hosted CI, and corrects its own stale "nightly was down" clause: three systemd user timers are active. V-8's latest line says no commit makes the four-shape rule automatic. It records the scratch `sigil build --game demo` in `build.sh` as partial cover that is explicitly "not a demo build".
- **Hosted CI today.** aeon has 0 GitHub workflow runs ever, and `.github` is 404 on the remote. aeon, sigil and oracle are all public. sigil has 1297 runs (last five success); oracle has 763 (last five: 1 failure, 4 success).
- **What the nightly does.** It builds four shapes plus the effects gates and the needs_build lane, taking 13 to 15 minutes of wall clock per night (journalctl).
- **The nightly's own record.** Its log since 2026-08-18 shows 18 all-gates-OK lines, 3 EFFECTS GATES FAILED and 14 COULD NOT RUN. The needs_build lane could not run on 09-08, 09-09 and 09-10, and 09-11 was all OK. The nine-night outage from 08-29 to 09-06, with nine unread critical alerts, is in the 2026-09-06 packet's Step 0 addendum.
- **The landing script.** `tools/landing_build.sh` is the four-shape build plus the needs_build lane. Its LS-1c closure calls it "a ritual like the effects gate, not a hook". It neither merges nor pushes.
- **Hooks.** No hooks are installed in aeon's `.git/hooks`, and `core.hooksPath` is unset.
- **Peer lanes.** Each of the other lanes has a landing command that gates the push: oracle's `tools/land.sh` (ten gates, pushes the tested SHA, about 25 minutes), aurora's `npm run land`, and sigil's `scripts/landing-run.sh`.
- **Why hosted CI costs days.** `build.sh` needs sigil's release binaries and the empyrean checkout, and the committed level tree's generators need out-of-repo donors. The effects gates boot a headless emulator.
- **Estimates.** The effort figures are estimates. The 10 to 15 minutes per merge comes from 150 to 160 s per shape (LS-14 evidence) plus the lane.

**Card JSON (dry-run file):**

```json
{
  "id": "CTRL-3",
  "question": "Before a change joins the main copy of the game, all four builds (Sonic 4 and the small demo game, each in normal and debug form) are supposed to be built and checked, but today that rests on someone remembering to run one command, and the overnight jobs on your PC catch a skipped run the next morning at best. Should that stay a habit, become a command that refuses to merge unless every check passed, or move to GitHub's automatic checks on every upload?",
  "options": [
    {
      "key": "ritual",
      "name": "Keep the habit and the overnight jobs",
      "what": "Nothing changes. The check command is run by hand before each merge, and three jobs on your PC re-check the main copy every night between about 4 and 7 in the morning.",
      "costs": "No new work. A skipped run is caught the next morning at the earliest, and only when the PC was on and the night job itself worked: in late August and early September it failed nine nights in a row while its alerts went unread, and this week it could not finish its full check on three nights out of five."
    },
    {
      "key": "gate",
      "name": "Make the check command the only way to merge",
      "what": "The command that builds and checks all four versions also does the merge and the upload, and refuses both if any check failed or the code changed during the run. The emulator and editor projects already land their work this way.",
      "costs": "About half a day to a day of work to build (an estimate). Every merge then waits for the full check, roughly 10 to 15 minutes on your PC, run in the background. Someone can still get around it on purpose, but nobody can skip it by forgetting."
    },
    {
      "key": "hosted",
      "name": "Add GitHub's automatic checks on every upload",
      "what": "GitHub builds and checks the game on its own machines whenever work is uploaded, and shows a red or green mark on the project page.",
      "costs": "Free for a public project like this one. But the game only builds with the matching version of our assembler and sound tool, two sibling projects, and for the effects checks the emulator too, so getting it running on GitHub's machines is several days of setup (an estimate) and it breaks whenever those move. It reports after the upload, so a bad merge is flagged once it is already on the main copy. The emulator project's GitHub checks once stayed red for 46 days before anyone read them."
    }
  ],
  "recommend": {
    "key": "gate",
    "because": "Every failure on record here is the same kind: a check that was supposed to happen and quietly did not. Making the command do the merge removes the step that gets skipped, needs nothing outside your PC, and matches how the other projects already land. GitHub's checks can still be added on top later if you want a public red or green mark."
  },
  "detail": "ONE CARD FOR TWO LEDGER ROWS: CTRL-3 (no hosted CI) and V-8 (the four-shape rule has no automation). V-8's own enforcement options are 'a merge hook, or CI per CTRL-3' (docs/superpowers/notes/2026-09-11-lens-open-sift.md, Bin C), so every answer to one answers the other: `ritual` leaves both open-by-choice, `gate` closes V-8 and answers CTRL-3 as 'local, no hosted CI', `hosted` answers CTRL-3 and closes V-8 after the fact. Two cards would let one answer leave the other reading as unanswered. EVIDENCE, measured 2026-09-11 unless dated: `gh api repos/Volence/aeon/actions/runs --jq .total_count` = 0 and `repos/Volence/aeon/contents/.github` = 404; aeon, sigil and oracle are all PUBLIC (`gh repo view --json visibility`); sigil has 1297 workflow runs (last five success), oracle 763 (last five: 1 failure, 4 success). `systemctl --user list-timers`: aeon-effects-gates 04:17, sigil-source-gates 05:17, sigil-ref-drift 07:17. The nightly (tools/nightly_effects_gates.sh) builds FOUR shapes plus the effects gates and the needs_build lane; journalctl wall clock 13-15 min per night. Its own log (~/.local/state/aeon-nightly/nightly.log, since 2026-08-18): 18 'all gates pass', 3 'EFFECTS GATES FAILED', 14 'COULD NOT RUN'; needs_build lane OK 6 times, COULD NOT RUN 3 (2026-09-08, 09-09, 09-10); 09-10 also EFFECTS GATES FAILED; 09-11 all OK. The nine-night outage 08-29..09-06 with nine unread critical notifications is packet 2026-09-06 'Step 0 addendum'. tools/landing_build.sh (LS-1c, closed 2026-09-10) IS the four-shape build and the needs_build lane, but its own closure row says 'a ritual like the effects gate, not a hook -- nothing in this tree mechanically blocks a merge'; it neither merges nor pushes. No hooks in /home/volence/sonic_hacks/aeon/.git/hooks (non-sample count 0), core.hooksPath unset. Per-shape build time 150-160 s (LS-14 evidence, load avg 5.7-6.8), so four shapes are ~10 min before the lane: the 10-15 min figure is that plus the needs_build lane, an estimate. HUB STANDING: 2026-09-05T22:48:31Z OVERSEER-LOG 'Pre-push hook enforcement put to the hub: RULED available not mandated tonight (a hook is per-lane local config; each lane may install one running its own landing command; revisit in the protocol pass)'. So `gate` needs no hub ruling. Peers: oracle tools/land.sh (483 lines, ten gates, pushes the tested SHA by name, ~25 min, must be detached from an agent seat), aurora `npm run land` (refuses a dirty tree, a failing suite, HEAD moving under the run and a no-op push; pushes the tested SHA; does not merge or write the log), sigil scripts/landing-run.sh. HOSTED COSTS, the parts that are not guesses: build.sh hard-requires SIGIL_BUILD and SIGIL_EMIT (sigil release binaries), resolves the empyrean checkout through tools/suite_paths.py (build.sh ~:583), the committed level tree's generators need out-of-repo donors (build.sh staleness-gate comment), and the effects gates boot a headless emulator per gate (CLAUDE.md). 'Several days' is an estimate. The 46-day figure is packet 2026-09-06 Step 0 ('oracle's sweep found its GitHub CI red since 2026-07-22, unread for 46 days')."
}
```

**Dry-run output:**

```
⚠ HUB OPEN-LIST CHECK, at file time:
  - COULD NOT CHECK the hub's open list (CalledProcessError). That is NOT a clean check -- it is an absent one. Read it by hand before filing: git -C ../empyrean show origin/main:docs/OVERSEER.md
  If this question is already answered or already listed for him, do NOT file: two framings of one decision means he answers one and the other reads as dealt with. Re-check before proceeding.
OK: 'CTRL-3' would be accepted by the reader; --check-only, nothing written
exit=0
```

---

## Card 2: `EFX-2`

**Evidence.**
- **The ledger row.** Its latest line (09-09T14:55) says the cross-fade is wired: `Effects_InstallPreset` arms `Palette_ArmFade` when a preset's transition is non-zero. It is unreachable because content never sets it, and it was left open deliberately as a content parcel.
- **What the tree shows.** Re-measured: nine sites, all passing `pal: OJZ_Palette`. The editor's effects `transition` field is the raster-scene transition, so no authoring surface reaches the palette cross-fade.
- **Sizes.** Read from the main checkout's `s4.lst` (2026-09-10, not rebuilt for this note), so they are approximate: 98 B of RAM (`Pal_Target` 96, plus two one-byte cells); about 210 B of fade code (`Palette_ArmFade` 8, `Palette_DoFade` up to 202); and 18 B of preset fields across the nine presets.
- **Deletion.** Removing the fade shifts the preset struct, so it is byte-moving. All the non-`keep` options carry the effects-gate ritual.
- **The recommendation.** It leans on precedent d-53, where the owner said "Sure let's do it to see it?". It also leans on two items that come from lane memory, not from this tree: the seamless multi-zone act goal, and the owner's preference against dormant code. The detail says so.

**Card JSON (dry-run file):**

```json
{
  "id": "EFX-2",
  "question": "The engine can smoothly fade the level's colours when the player crosses into a new part of a level, but nothing in the game uses it, and every part of the first level uses the same colours, so there is nothing to fade between yet. Should we try it on screen in the first level, delete it, or keep it switched off for later?",
  "options": [
    {
      "key": "show",
      "name": "Try it in the first level",
      "what": "One section of the first level gets its own set of colours, for example a darker or cooler tint, and crossing into it fades over about a quarter of a second instead of switching at once.",
      "costs": "You pick or approve the second set of colours, and it is about a day of our work (an estimate) including the effects checks. If you do not like it on screen, deleting it afterwards is still open and costs the same as deleting it now."
    },
    {
      "key": "delete",
      "name": "Delete the fade",
      "what": "The fade is removed. Crossing into a new section keeps switching colours at once, as it does today.",
      "costs": "About a day of our work (an estimate). It frees about 100 bytes of working memory and roughly 250 bytes of cartridge space. If a later level wants a smooth colour change between areas, such as a level that runs straight from one zone into the next, it has to be built again."
    },
    {
      "key": "keep",
      "name": "Keep it switched off",
      "what": "Nothing changes. The fade stays in the game, switched off everywhere.",
      "costs": "No work now. It keeps using about 100 bytes of working memory, and because it has never run in the game, any fault in it stays hidden until the day something first uses it."
    }
  ],
  "recommend": {
    "key": "show",
    "because": "It is cheap to see, and a level that runs seamlessly from one zone into the next, which you have set as a goal, is exactly where a colour fade earns its place. Seeing it once tells us whether it works and whether you like it, so the later choice between keeping and deleting it is made with something on screen. Keeping it switched off is the one answer I would avoid, since it carries code that has never run."
  },
  "detail": "EFX-2 latest ledger line (docs/lens-findings.jsonl): the cross-fade is unreachable because every preset takes transition's default of 0, open deliberately as a content parcel's behavioural delta. RE-MEASURED 2026-09-11 at origin/master 6d4b5656: there are NINE real `preset(...)` call sites, all in games/sonic4/data/effects/ojz_effects.emp (OJZ_Preset_Sec0/1/2/3/Plain/Depth/5/6/7). The ledger's and the sift's 'ten' counted a COMMENT at games/sonic4/data/generated/ojz/act1/effects_scenes.emp (the `//     pub data OJZ_Preset_SecN ... preset(pal:` template line). ALL NINE pass `pal: OJZ_Palette`, so arming the fade today would lerp OJZ_Palette into itself: zero visible change. That is why `show` needs a second palette, which is content and his eye call. Mechanism: Effects_InstallPreset (engine/effects/preset.emp) tests EffectsPreset.ep_transition and calls Palette_ArmFade before Palette_LoadPal; the armed load fills Pal_Target and sets Pal_Fade_Frames = PAL_FADE_FRAMES (16); Palette_DoFade steps each channel +/-1 on even frames, so 16 frames is about 0.27 s at 60 Hz. The editor's effects JSON field `transition` (\"instant\"/\"smooth\") is the SCENE transition (tools/effects_gen.py TRANSITION_NAMES), unrelated: no authoring surface reaches ep_transition. SIZES, read from the main checkout's s4.lst (mtime 2026-09-10 01:23, NOT rebuilt for this note, so approximate): Pal_Target $FFFF8D8E..$FFFF8DEE = 96 B, plus Pal_Fade_Frames and Pal_Fade_Request 1 B each = 98 B RAM; Palette_ArmFade $733A..$7342 = 8 B; Palette_DoFade $74B0..$757A = 202 B (upper bound: the span includes inline step blocks asm10..asm12 whose ownership was not checked); ep_transition is a u16 in each of 9 presets = 18 B; plus the arm branch and the compose dispatch. 'Roughly 250 bytes' is that sum, an estimate. `delete` shifts the EffectsPreset layout (ep_patch_motion follows ep_transition at $26), so it is byte-moving; any of the three non-`keep` options touches engine/effects/* and so carries the effects-gate ritual (CLAUDE.md). 'About a day' for show/delete is an estimate. PROVENANCE OF THE RECOMMENDATION: precedent d-53 (owner 2026-09-03, quoted at ojz_effects.emp OJZ_Preset_Sec5: 'Sure let's do it to see it?') gave a dormant raster channel a consumer so he could see it. The seamless multi-zone mega-act goal and the owner's stated preference against dormant scaffolds ('clean, not bolted-on') are from the lane's memory, not from this tree."
}
```

**Dry-run output:**

```
⚠ HUB OPEN-LIST CHECK, at file time:
  - COULD NOT CHECK the hub's open list (CalledProcessError). That is NOT a clean check -- it is an absent one. Read it by hand before filing: git -C ../empyrean show origin/main:docs/OVERSEER.md
  If this question is already answered or already listed for him, do NOT file: two framings of one decision means he answers one and the other reads as dealt with. Re-check before proceeding.
OK: 'EFX-2' would be accepted by the reader; --check-only, nothing written
exit=0
```

---

## Card 3: `B1-6`

**Evidence.**
- **The ledger row.** Its latest line (09-09T00:45) says no magic-number lint exists anywhere, and s4lint is retired.
- **The two groups found so far.** Both were locked by per-family `ensure` pins, each proven to fail when it should: LS-8 (closed 09-10) and LS-8a (closed 09-11, merge `f1b3fae6`).
- **Why a text lint misses the case.** LS-8's re-enumeration found 45 sites where the row counted 21, including shift-add chains with no literal in them.
- **Measured counts.** These come from an anchored grep, so they are approximate. There are 1,644 instruction lines with a numeric immediate across 197 `.emp` files. Of the `andi` lines, 116 use a literal mask and 115 a symbolic one.
- **Estimates.** The effort figures are estimates.
- **Lane or owner?** This is arguably a lane call rather than an owner call. It is drafted because the sift binned it C, and because it sets a standing policy ("no tree-wide lint") that the owner can overturn with one word.

**Card JSON (dry-run file):**

```json
{
  "id": "B1-6",
  "question": "Some sizes in the engine are typed as plain numbers in several places instead of using the one named setting they depend on, so if that setting is ever changed the copies keep the old value and nothing complains. We have been locking these down one group at a time with a build check that fails when the copies and the setting disagree; should we also build a tool that hunts for plain numbers across the whole engine?",
  "options": [
    {
      "key": "per_group",
      "name": "Keep locking them down one group at a time",
      "what": "When a review finds a group of copied numbers, that group gets its own build check, as the last two groups did. No new tool.",
      "costs": "Nothing new to build or maintain. A group nobody has reviewed yet stays unguarded until a review finds it; each of the last two groups took one small job to lock down."
    },
    {
      "key": "narrow",
      "name": "A tool for the one pattern that caused trouble",
      "what": "A tool flags only the kind of number behind the problem: grid and wrap-around masks typed as plain numbers.",
      "costs": "About a day to build and a day to go through the roughly 116 places it would flag today, most of them fine (estimates). It cannot see the cases where the same size hides inside arithmetic with no number typed at all, and the last fix found exactly those."
    },
    {
      "key": "broad",
      "name": "A tool for every plain number",
      "what": "A tool flags every plain number in the engine's code, and each one is either given a name or marked as intended.",
      "costs": "Several days of going through about 1,600 numbers, most of them hardware values that are correct as typed (an estimate), then warnings on everyday work from then on. The last two broad checking tools proposed here were declined or retired, one because the code breaks its rule on purpose and one because it had ended up checking almost nothing."
    }
  ],
  "recommend": {
    "key": "per_group",
    "because": "The job that closed the last group found that the dangerous copies included ones with no number typed at all, which neither tool can see, and its checks caught every case in that group, each one shown to fail when it should. A number-hunting tool would spend days sorting harmless numbers and still miss the cases that matter most."
  },
  "detail": "B1-6 latest ledger line: neither tools/s4lint.py (now RETIRED, LS-14) nor the sigil lint registry carries a magic-mask or magic-number lint (packet 2026-09-06 seat B1, 'B1's second open item'). THE TWO GROUPS: LS-8 (closed 2026-09-10, parcel/ls8-mask-family-pins: 11 new ensures + 5 rewritten messages, 16/16 guards red-first) and LS-8a (closed 2026-09-11, parcel/lens-pins-0911, merge f1b3fae6: plane-wrap masks). LS-8's re-enumeration 'by what TOUCHES the value' found 45 sites where the row counted 21, including two row-stride sites hand-rolled as ((x<<2)+x)<<4 that 'contain no literal 80 at all, so the immediate grep that found the other four cannot see them', and the '17 masks' were two different constants that are both 16 today. That is the load-bearing fact against a text lint. COUNTS, measured 2026-09-11 over engine/ and games/ *.emp with a simple anchored grep (code lines only, comments excluded by anchoring, so approximate): 1,644 instruction lines with a numeric immediate (#$hex or #decimal) across 197 .emp files; `andi` with a literal mask 116, with a symbolic mask 115. PRECEDENT, stated precisely because the brief's summary of it was broader than the rows: LS-2 (closed 2026-09-07, b83204df) DECLINED a lint for 68000 clobbers over-declaration for three stated reasons (the codebase over-declares on purpose with written rationale, so a lint would need a suppression attribute on day one; not a correctness class; narrowing pressure is byte-moving in sigil). LS-14 (closed 2026-09-07) RETIRED s4lint because its subject had collapsed to one 8-line file with zero instructions, not because it was heuristic. LS-14a keeps six real invariants with no .emp-side check open. A magic-number lint in the language itself would be sigil's (cross-lane); an aeon-side one would be a Python text scan. 'About a day', 'several days' are estimates."
}
```

**Dry-run output:**

```
⚠ HUB OPEN-LIST CHECK, at file time:
  - COULD NOT CHECK the hub's open list (CalledProcessError). That is NOT a clean check -- it is an absent one. Read it by hand before filing: git -C ../empyrean show origin/main:docs/OVERSEER.md
  If this question is already answered or already listed for him, do NOT file: two framings of one decision means he answers one and the other reads as dealt with. Re-check before proceeding.
OK: 'B1-6' would be accepted by the reader; --check-only, nothing written
exit=0
```

---

## Card 4: `CHAR-10`

**Evidence.**
- **The ledger row.** Its latest line (09-09T14:55) says `Character_ID` has one writer, `ojz_scroll_test.emp:1586`, re-verified today. That writer stands down under both playback and record.
- **What goes untested.** The two fixtures (1721 and 2350 ticks, per `replay_pack.py dump`) are Sonic-only by construction. Six player states have zero automated coverage: Tails has one, flying; Knuckles has five, gliding, glide-falling, sliding, climbing and ledge moves. Both ability hooks and every per-character asset path are also uncovered.
- **Why it is his call.** DEFERRED_WORK records that re-recording the owner's regression net is his decision (d-14, 2026-08-26).
- **Pixel-blind.** The replay net hashes player state and never looks at the picture (DEFERRED_WORK, 2026-09-10 re-record handoff).
- **Which lane holds it.** See ruling 2 for the lane split and oracle's header validation.
- **The mechanism is the lane's call.** The card leaves out whether the character travels as a header byte or a boot seed.
- **A constraint to check before promising a route.** Oracle's driver cannot press C, so a Knuckles glide route has to be checked against that first.
- **Estimates.** The effort figures are estimates.

**Card JSON (dry-run file):**

```json
{
  "id": "CHAR-10",
  "question": "Our automatic play-through tests always play as Sonic and have no way to switch character, so Tails' flying and Knuckles' gliding, climbing, sliding and ledge moves have never been checked by anything except people playing. Should recorded test runs be able to play as Tails and Knuckles?",
  "options": [
    {
      "key": "both",
      "name": "Add recorded runs for Tails and Knuckles",
      "what": "A recorded run can say which character it plays. We record one run where Tails flies and one where Knuckles glides, climbs and slides, and they join the two Sonic runs that already guard the first level. These runs check where the character goes and what state and animation it is in; they do not look at the picture, so a wrong colour like the red spring's under Knuckles would still be caught only by eye.",
      "costs": "Roughly two to three days across our team and the emulator team (an estimate), because the emulator's test player has to learn the new setting too. After that, each deliberate change to how the characters move means refreshing three characters' runs instead of one; the refresh is one automatic pass each, and each is your call, as the Sonic one was in August."
    },
    {
      "key": "knuckles",
      "name": "Knuckles first",
      "what": "The same, but only Knuckles gets a recorded run for now. He has five of the six moves nothing checks today.",
      "costs": "Almost all of the cost of the full option (an estimate), because the hard part is teaching the tests to pick a character at all. Tails' flying stays checked only by people playing."
    },
    {
      "key": "leave",
      "name": "Leave it; character checks stay by hand",
      "what": "The tests keep playing as Sonic. Tails and Knuckles are checked when you or we play them.",
      "costs": "No work. A mistake in how Tails or Knuckles moves reaches you first, the way the spring's colour under Knuckles did."
    }
  ],
  "recommend": {
    "key": "both",
    "because": "Nearly all of the cost is teaching the tests to choose a character, and once that exists a second recording is cheap. It puts an automatic check under the moves only two of the three characters have, which today nothing but people playing ever touches. It will not catch colour mistakes, which stay an eye check whichever you pick."
  },
  "detail": "CHAR-10 latest ledger line (from the 2026-08-13 character sweep, item D2): Character_ID has exactly ONE write site, `move.w d0, Character_ID` in Debug_CharacterHotkey (games/sonic4/test/ojz_scroll_test.emp, re-verified 2026-09-11 at :1586), gated first on `tst.b Input_Source` so it stands down under playback AND record, and also on DEBUG and PlayerV.debug_flag. So every ARP0 fixture runs as CHAR_SONIC by construction; PSTATE_FLY (Tails) and PSTATE_GLIDE/GLIDEFALL/SLIDE/CLIMB/LEDGE (Knuckles: five of six), both ability hooks and the per-character asset paths have zero automated coverage. The two fixtures today: games/sonic4/data/replays/ojz_fixture.bin (1721 ticks, 27 checkpoints) and ojz_slide_fixture.bin (2350 ticks, 37 checkpoints), per `tools/replay_pack.py dump`. WHY THE CARD SAYS 'DOES NOT LOOK AT THE PICTURE': Replay_Hash covers Player_1's address-free SST fields (position, velocity, status, animation, art_tile...) and never CRAM; DEFERRED_WORK 'REPLAY RE-RECORD -- handed over by oracle' (2026-09-10) states the net is PIXEL-BLIND. The spring palette slip (SPRING-PAL-IDX9) is therefore NOT something a Knuckles fixture would have caught; the ledger row itself says the coverage hole is why nothing caught a per-character path, not the cause, and the card keeps those apart. WHY IT IS HIS CALL: DEFERRED_WORK's 2026-08-26 replay entry, 'Re-recording the owner's regression net is therefore his call' (ruled as d-14, executed by `replay_runner --restamp` in one pass). CROSS-LANE, AND WHY AEON FILES IT (contract rule 10): the fixture FORMAT and the in-ROM recorder are aeon's (engine/system/replay.emp, INPUT_RECORD DEBUG-only; tools/replay_pack.py, spec docs/superpowers/specs/2026-08-02-input-replay-design.md). ORACLE owns the headless runner and restamp (oracle origin/main adcf2395, crates/oracle-replay/src/header.rs), and that runner REFUSES a non-zero `pad` (offset 5) or `reserved` (offset 18) byte, so a character byte in the header needs a matching oracle change. Oracle's ledger at origin/main adcf2395 (50 lines) has no card on replay character selection (grep for replay/fixture/character/knuckles/tails/seed/record hits d-10, d-15, d-16, d-34, d-35, d-40, d-45, none about this); origin/master is a stale June branch (2908bbd2, 2026-06-24). The firsthand measurement (the single writer, the playback gate) is aeon's, so aeon holds the one card and oracle references it. MECHANISM, the lane's call and deliberately not on the card: a character id in the ARP0 header (the flags byte's reserved bits, or `pad` / `reserved`) read at playback entry, with games/sonic4/player/characters.emp accepting it at boot (it refuses a poked Character_ID that desyncs). A boot seed poked by the runner is the alternative; 'one fixture per character' is the content under either. Recording constraint on record: the oracle driver cannot press BUTTON_C (DEFERRED_WORK, same 2026-08-26 entry), which a Knuckles glide route must be checked against before promising it. Effort figures are estimates."
}
```

**Dry-run output:**

```
⚠ HUB OPEN-LIST CHECK, at file time:
  - COULD NOT CHECK the hub's open list (CalledProcessError). That is NOT a clean check -- it is an absent one. Read it by hand before filing: git -C ../empyrean show origin/main:docs/OVERSEER.md
  If this question is already answered or already listed for him, do NOT file: two framings of one decision means he answers one and the other reads as dealt with. Re-check before proceeding.
OK: 'CHAR-10' would be accepted by the reader; --check-only, nothing written
exit=0
```
