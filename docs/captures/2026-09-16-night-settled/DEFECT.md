# ⚠ THIS SET CARRIES A TOOL DEFECT. Read this before its README.

This is the **first live run** of `tools/night_settle_capture.py` (2026-09-16, `s4.debug.bin`
md5 `63980e7e`, capture exit 0). It is kept, not deleted, because it is the evidence for a
defect in the tool that produced it. A later run supersedes it; this one stays.

## What is sound here

The three frames named `settled` — `in-k+006`, `in-k+007`, `in-k+008` — **are** settled, and
the predicate earned its keep on its first real outing. `Pal_Fade_Frames` runs 15, 14, 13, 12
and then straight to **0** at `k = +4`: the `.arrived` early close. A tool naming frames on
`Pal_Fade_Frames == 0` would have stamped `settled` on `k = +4`, two ticks before CRAM had
been stable long enough for the captured frame to show it. This one said `hold` and waited.
That is the whole point of the parcel, working.

## What is wrong here

**Every `k < 0` frame is named `buf` and none was certified, and all four were settled.**
Measured from this set's own `report.json`: at `k = -4` the day palette had been bit-identical
in CRAM for **194 consecutive samples**, `buffer == cram`, `Pal_Fade_Request` 0, `Pal_Op` 0,
`Pal_Base_Dirty` 0, `Pal_Active` = `PAL_ACT_VARIANT` only.

The `buf` clause compared `Palette_Buffer` against `Pal_Target` and found 42 of 48 words
differing — because **`Pal_Target` was 48 words of `$0000`, never written.** Its only writer
in the tree is `Palette_LoadPal`'s fade arm (`engine/effects/palette.emp:302`), and no fade had
run that session. The clause's premise was not false, it was **silent**, and the clause treated
silence as disagreement.

**And the refusal named a mechanism that did not occur.** Its reason read *"The fade STOPPED
rather than arrived (Palette_LoadPal's snap arm clears the count)"* on a run where no fade had
ever started. That is worse than a green that means less than it appears: it aims the next
person's search at something that is not there.

The visible symptom, in this set's own README, is a sentence that contradicts itself:

> The **0** approach frame(s) before the crossing are also named `settled`

That line — and the `0 day-palette controls` on the tool's stderr — was the finding, printed,
and read past by two people. A control that returns zero and is not read is its own defect.

## Why it mattered

The `k < 0` frames are the **day baseline** the night colour is judged against. This set
therefore offers three certified night frames and **no certified day frame to compare them
with**: half a deliverable.

## What was done

`buf` now runs only where the observed series establishes that `Pal_Target` is authoritative
(a fade seen in flight, no snap install since). The unset case was the instance; the premise
was wrong in general — a snap install never updates `Pal_Target` either, so every frame after
the snap-back at x = 4800 would have been refused the same way. What keeps a half-stepped
buffer out of a certified frame is clauses 1-3, which are exhaustive over the *writers* of
`Palette_Buffer` via the engine's own frame-top committer census. See
`tools/capture_settle.py`'s header, section "WHEN `Pal_Target` MEANS ANYTHING".

A zero control count is now a named report field, a loud stderr banner and a README banner.

## Superseding this set

Do not re-run into this directory — the tool now refuses, because its PNGs are named from
state and a second run would leave this run's frames beside the new ones under a README
describing only the new ones. Pass a fresh `--outdir`; this set stays as the record.
