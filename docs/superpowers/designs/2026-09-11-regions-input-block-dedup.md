# Regions planning input: intra-section block dedup (the owner's idea capture)

**Whose and why it is here.** This is the OWNER's idea, captured 2026-09-11 by a session of his into
`docs/DEFERRED_WORK.md` and left uncommitted there. Asked whether it was his and whether to keep it, he
answered, verbatim (heard directly by the hub; empyrean `1bd4a36`, `docs/OVERSEER-LOG.md`, entry
"2026-09-11T19:11:04Z owner answer on aeon's uncommitted block-dedup note"): *"it was and yyes, I wanted
something added to the region project and the agent put it in there if you want to put it in the region
project"*. So it lives with REGIONS (`docs/superpowers/designs/2026-09-09-regions-v1-design.md`) as
**planning input, not work to build now**; the REGIONS start gate ("only when it's at a good spot") is
unchanged. Moved here by the aeon overseer 2026-09-11T19:13:04Z. The text below is the note **byte-for-byte as he
left it** (82 lines, sha256 `9a4d88f1...`), including its own corrections and its own statement that
its falsifier is the first task.

---

## Intra-section block dedup — idea capture 2026-09-11

**Framing:** an S2 chunk existed so an author could place the same 128x128 stamp two hundred
times and pay for it once. Our block has the chunk's exact geometry (16x16 cells, 512 B
nametable + 2x128 B collision = 768 B raw) but not that job. Dedup today happens only at the
whole-section-blob level (`tools/ojz_block_gen.py:597`, "identical block blobs collapse to one
BINCLUDE" — that is what makes OJZ sec4 a zero-byte alias of sec2). Within a section nothing
collapses. Duplicate terrain survives only because S4LZ's per-section dictionary compresses a
repeated block down to near one long match.

**Measured 2026-09-11** against `games/sonic4/data/generated/ojz/act1/sec*_blocks.bin`:
- 497 live block slots across the 9 sections, and **497 distinct index offsets** — zero
  intra-section collapse, as the generator implies.
- Cost per unique block: (file bytes - 1024 B index) / unique count = **54-116 B, mean ~87**,
  against 768 B raw.
- Blobs total 53,064 B; 47,024 B in ROM after the sec4 -> sec2 alias.

**The lever.** If two slots in a section hold identical bytes, deduping makes the second free —
its 4-byte index entry is already paid — instead of costing ~87 B of LZ match. Prize is
therefore ~87 B per duplicate block.

**FALSIFY THIS FIRST, IT IS CHEAP.** I did NOT compare block *contents*. I compared index
offsets, and distinct offsets do not prove distinct bytes. Hash the 768 B raw blocks per section
and count distinct — ten lines against the same generator. If intra-section duplicate content is
rare, this entry is worth nothing and should be struck rather than carried. OJZ is also the
weakest possible witness for a lever whose payoff scales with density: 48-88 live of 256 slots
per section.

**Why it is worth looking at anyway.** The payoff scales with exactly what the mega-act goal
adds — dense sections carrying repeated terrain. A rough projection during the 2026-09-10 owner
conversation put an all-of-Sonic-2-in-one-act tilemap at 0.7 MB (OJZ-sparse) to 2.2 MB (dense,
~160 live blocks/section) over ~140 sections: the difference between comfortable and over-budget
in a 4 MB image. That projection is an estimate built on the 87 B mean, not a measurement of any
real dense content, and the ~140-section figure is derived from Sonic 2's `LevelSize` camera
bounds (`s2disasm/s2.asm:14698`), several of which are the `$3FFF` unbounded sentinel.

**Triggers to pick it up:** a section's live-block count rises materially above OJZ's ~55; the
multi-zone / mega-act work starts producing real layouts; or anyone re-opens the S4LZ
per-section dictionary sweep (K = 0..3), since block identity and dictionary-seed choice
interact.

**Not covered by regions.** `REGIONS-V1-WORTH-IT` buys off-grid effects/parallax boundaries at
+152 B; it touches neither block identity nor the block stream. Nothing else in the tree books
this.

**CORRECTED 2026-09-11, same day, by the owner's challenge ("that 768 to 87 is kind of skewed
yeah?"). He was right and the entry above understates the lever. Original text kept above.**

The 87 B mean hides a bimodal distribution. Per-block compressed sizes across OJZ act 1's 488
compressed blocks (sizes derived as gaps between sorted index offsets, plus 9 raw-direct dict
blocks at 768 B):

| min | p10 | median | mean | p90 | max |
|---:|---:|---:|---:|---:|---:|
| 12 | 26 | **28** | 76 | 276 | 420 |

66.6% of live blocks compress to <= 32 B, 76.8% to <= 64 B. That is uniform fill (solid sky,
solid ground), not terrain. **A block carrying real detail costs 276-420 B.** The planning
number for dense content is therefore ~300 B per block, not 87, and the mean is an artifact of
OJZ's fill-heavy mix rather than a property of the format.

**Two claims above are now wrong, not merely imprecise:**

1. *"Duplicate terrain survives only because S4LZ's per-section dictionary compresses a repeated
   block down to near one long match."* FALSE for all but K blocks per section. Per
   `tools/ojz_block_gen.py`, each block is compressed independently against the dictionary
   window ONLY, not against its neighbours, and OJZ's swept optimum is K=1. So exactly one
   duplicate per section gets that treatment; every other duplicate pays full freight.

2. *"Prize is therefore ~87 B per duplicate block."* UNDERSTATED. The prize is the duplicate's
   own full compressed cost, which for detailed blocks is 276-420 B. Roughly 3.5x the figure
   booked above, and the gap widens with density because density shifts the mix toward the
   expensive tail.

**The mega-act projection above (0.7-2.2 MB) is correspondingly optimistic at its top end** and
should be re-derived from the distribution rather than the mean before anyone plans against it.

**The falsifier is unchanged and still the first task:** hash the 768 B raw blocks per section
and count distinct content. Everything here prices what a duplicate COSTS; none of it
establishes that duplicates EXIST in any quantity.


