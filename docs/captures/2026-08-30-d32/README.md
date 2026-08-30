# d-32 left-edge re-measure — the captures behind a RETRACTED result (2026-08-30)

These four frames are the evidence for the d-32 re-measure booked in
`docs/DEFERRED_WORK.md`, section **"d-32 RE-MEASURE — RETRACTED THE SAME NIGHT IT WAS
MADE, AND THE FAILURE IS INSTRUCTIVE"**. Read that entry first. **The result they were
taken to support was withdrawn within the hour and d-32's status is UNKNOWN**, exactly as
it was before the measurement.

They are kept because a retracted measurement's frames are worth more than a clean one's:
they are what the wrong answer actually looked like.

| file | what it is |
|---|---|
| `scene00-wholeplane-control.png` | the whole-plane control |
| `scene14-percolumn-subject.png` | the per-column subject the claim was read off |
| `scene14-dense-frozen.png` | the dense variant, frozen |
| `scene14-offgrid-frozen.png` | the off-grid attempt |

**Why the subject frame cannot answer the question, and this is the durable part.** The
sliver under test is `hscroll & 15` pixels wide, and the frozen sample sat at
`Camera_X = 3984` — which is `249 x 16`. **A 16-aligned camera has a zero-pixel sliver by
construction**, so a clean reading was the only reading available, fix or no fix. The
retry did not clear it either: a 60-frame nudge landed on 1472, aligned again, where the
foreground is additionally empty across x 0-23.

**What a correct measurement still needs, both conditions in ONE frame:** a camera X that
is not 16-aligned, AND plane A content actually present at the left edge. Whether this
harness can ever settle a camera off-16 is itself unestablished and worth answering first.

*Provenance: captured 2026-08-29T21:41-21:58 local by a session that has since ended.
Filenames and timestamps are the whole of what identifies them; the mapping above is read
off those and off the retraction entry, not off a record the capturing session left.*
