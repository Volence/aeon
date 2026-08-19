# Profiler shape answers + CR-26 pre-build check (2026-08-19)

Aeon-side anchor for the answers relayed to oracle-next during their profiler recon
(their demand doc §10 records them as transcription-not-quotation pending this anchor),
and the verdict of the pre-build shape check on CR-26.

## The three answers, as given

1. **Inclusive is the parity field.** Every consumer we have reads rows inclusively: the
   F-series takes the HBlank trampoline's row as the whole fire including callees; the
   Task-4 walker-fit method (vary one feature, read the marginal) prices callees inside
   the caller's row by construction. `cyclesSelf` is welcome for future attribution,
   consumed by nothing today.
2. **`cycles - stallCycles == derived_constant` is the right gate form**, with two pins
   (both now normative in their fragment): stallCycles keyed identically to cycles with
   the same divided-inside exactness, and the stall definition ENUMERATED so a new stall
   source is an amendment event, not silent drift. Their stall finding (old oracle's
   clock excludes stalls, M68000.cpp:1029-1031) also explains why our ==-derived cost
   gates have matched that instrument exactly — its clock is ideal-cycle by construction.
   That is now an explicit caveat on every Phase-0 corpus row, and Task 5's DMA-stall row
   records instrument-blindness rather than a confident undercount (corrected mid-session).
3. **perFrame[] is record-and-later.** The 30→31 effective-frame change on migration
   (their frame-aligned arming deletes the old ring's runt frame 0) is flagged in our
   migration notes, with the deletable arm/drain sleeps and the `frames`-param removal
   (`frames` without perFrame armed refuses -32005 — first-run breakage if uncaught).

## CR-26 pre-build shape check — PASS

Reviewed at oracle-next `4cf7db5` (`docs/2026-08-19-cr26-profiler.md` + ruling; contract
draft empyrean `profiler-amendment` @ `a4002fb`). Verified against
`tools/raster_cost_probe.py`'s real consumption:

- Row shape {addr 24-bit canonical, name/disp, cycles inclusive, cyclesSelf, stallCycles,
  calls} covers every field the probe reads and deletes its two reconciliation hacks
  (sign-extension trim, address-only matching).
- **M2** (divisor: n boundaries = n−1 whole frames, opening boundary excluded) makes the
  divided figures unambiguous — the property our exact `==` gates rest on.
- **M3** (bucket edges): opens at acknowledge, closes at the RTE unwinding that
  interrupt's own frame; an unmatched RTE closes nothing and a server MUST NOT
  retroactively open a bucket; `calls` counts taken, so raised-but-masked appears
  nowhere; nested cycles accrue to the nested bucket alone. All four properties are the
  ones our per-frame HInt total (P2 budget axis 4b) and fire-count correctness checks
  need. The TRAP-inside-handler case (trap's RTE never closes the interrupt bucket) is
  the exclusion that would otherwise have silently corrupted `vint` on the MD-debugger
  path.
- Arming not refused on a running machine (sample edges are frame boundaries) — required
  by our headless probes' drive pattern.

Implementation green-lit from our side on this shape. The parity-corpus A/B (P2 Phase 0
rows, SHA to be supplied at landing) is the primary acceptance, with the summed-`hint`
vs split-buckets delta pinned as a falsifiable equation, spread gated at exactly 0.
