# Chain 198 abandoned, and two corrections to prose that cannot be amended

**2026-09-02.** Written because `--supersede-tip` is a one-line ledger field and this does not
fit in one line. Entry 198's ledger row points here; this is the argument the row cannot carry.

A frozen entry cannot be edited. So where 198's own `ab` prose is **wrong** — not merely
superseded — the correction has to live somewhere a later reader will actually meet, and be
worded so it cannot be mistaken for "we have newer numbers".

## Why 198 was abandoned

Its strict run went red: **4227 passed / 3 failed / 2 ignored**, `finished=1`, recorded at
sigil `dd5eaad2`. An entry is frozen once it records a strict run, so a red tip is abandoned
and replaced, never amended — and abandonment legally requires the recorded red run, which is
why that red was committed rather than tidied away.

All three failures were **harness composition, not output**:

- `act_descriptor_region_matches_reference` and its `_debug` twin, wanting item 5's two new
  cross-seam names `EditorRaster_OJZ_Act1_ojz_sec3_shimmer` and
  `EditorCycle_OJZ_Act1_ojz_sec3_shimmer` supplied to a scope that compiles one module
  standalone.
- `generated_pins_match_the_hand_typed_baseline`, wanting a per-parcel term for
  `DEBUG_ASSEMBLED_LEN` `0xA7F34 -> 0xA7F38`.

**No ROM byte moved.** 198's own `[entry.strict.goldens]` repeats the frozen CRC/size pairs
exactly. It was not the stale-instrument class either: `pins_rs_is_current` passed in the same
run, which is the documented discriminator.

## Correction 1 — 198's byte decomposition is WRONG, not superseded

198's prose reads *"release +93 = 62 content + 31 appendix; debug +100 = 62 + 4 + 34"*.

The deb2 appendix begins at **exactly** `EndOfRom` — magic `deb20402` read at that offset in
both ROMs, no padding — so `file_delta = assembled_delta + appendix_delta`, identically.

| shape | file Δ | assembled Δ | appendix Δ |
|---|---|---|---|
| s4 | 719347 → 719440, **+93** | 679042 → 679042, **+0** | 40305 → 40398, **+93** |
| s4.debug | 736354 → 736454, **+100** | 687924 → 687928, **+4** | 48430 → 48526, **+96** |

The parcel's 62 bytes of content are real and **do ship in both shapes** — they are org-anchor
absorbed at `0x90000` and never reach the file end, so they cannot be a term in a *file* delta.
The old prose counts them twice. **Entry 198's own held `s4 anchor_end = 0xa5c82` is the
refutation**: 62 bytes reaching the tail would have moved it.

How the error was produced, since that is the reusable part: the mechanism was corrected first
(the payload is absorbed *whole*, not partially), and the arithmetic that mechanism had produced
was then re-certified rather than re-derived — *"the arithmetic was right and the word 'leaving'
was the whole defect"*. The arithmetic was the wrong half. A refuted mechanism invalidates
everything built on it.

## Correction 2 — the +4 is IDENTIFIED, not inferred

It is the third `dc.l` row of `Debug_BandDemoHotkey`'s `.raster_table`, DEBUG-gated. The span
runs `0xA6886..0xA688E` (8 B) at chain 197 and `0xA6886..0xA6892` (12 B) at chain 198. **The
table start is unmoved**, which is what makes the +4 originate there rather than arrive from
upstream. The added longword reads `00013A96` in the image — `EditorRaster_OJZ_Act1_
ojz_sec3_shimmer`'s own address.

Reached over three enumeration parameters, checked to differ before the agreement was called
corroboration: listing delta classes; the span between two named symbols; and an exhaustive walk
of every delta transition plus a read of the ROM image. The third is a different *instrument*
from the first two, which is what makes it corroboration and not echo.

The alternative that produces the same +4 by a different mechanism — **partial absorption** of
the 62 content bytes — is refuted with plain as the control: both shapes carry the identical
`+0x3E` and both return to delta 0 at the same anchor.

Absence check, with a positive control rather than a bare empty grep: `grep raster_table s4.lst`
is **not** empty (it returns the unrelated equate `Sec_sec_raster_table`), so the missing table
label is a positive read of a non-empty result. `Debug_BandDemoHotkey` itself parks as a
zero-byte label at `0xA45DC` in the release listing — so *"the table does not exist in the
release shape"* is right, and *"the hotkey is debug-only"* would not be.

## Correction 3 — the cause of 198's red is not what this lane first recorded

It was attributed to a **skipped pre-flight**, in a commit message and in a committed lane-log
entry. That attribution is withdrawn.

`tools/freeze_preflight.sh` resolved its subject from **its own location** and tested the shared
main checkout, which does not contain the parcel. Measured: the composition under test appears
**0** times in that checkout's `pins.rs` and **once** in the landing worktree. So a pre-flight
run before 198 would have returned a green about a tree without the composition, and **could not
have warned anyone**.

*"The gate was skipped"* and *"the gate ran and could not see the subject"* leave identical
evidence, which is why the first is the story everyone reaches for. Fixed at aeon `1127080d`.

## The gap in 198 that cannot be closed

The binary that produced 198's goldens — sigil `079cec97`, md5
`956da96a78171ff99aa6fef229d59812` — was **overwritten in place** at the shared path and no
longer exists on disk. It is recoverable only by rebuilding at `079cec97`. Until someone does,
198 names an assembler nobody can re-instantiate by inspection.

*(That is the instance, and it belongs here because it is a property of this entry's provenance.
The general hazard — a shared assembler overwritten in place means any freeze's binary can cease
to exist — is a durable operational fact rather than a ledger fact, and lives in the sigil lane's
`OVERSEER.md` beside the relink bullet. Splitting them that way is the protocol's own rule: the
bar is durable, the precedent narrative is perishable.)*

## What 199 verified that 198 did not

Four canonical shapes rebuilt from a **fresh** clean worktree with the ROMs deleted first, all
four byte-identical to what 198 froze. That comparison is load-bearing rather than ceremonial:
had nothing been rebuilt, `--freeze` would have re-captured the goldens from the same files on
disk and the check could not have failed. It became a real question only because the shared
binary had moved (`956da96a -> 4ca83f71`), a fact nobody knew when the control was agreed.

Independently reproduced by the sigil lane's drift observer at a **later** aeon revision, with a
**different** compiler, in a different worktree, with its golden comparison derived as
not-applicable so nothing in it was trying to match. Different parameters, same bytes.
