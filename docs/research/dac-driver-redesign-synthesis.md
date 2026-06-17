# DAC Driver Redesign — Research Synthesis (2026-06-17, ultracode workflow)

Source: 8-agent parallel research (S3K/S2/S1/Flamedriver/sonic_hack Z80 drivers, Mega PCM 2.x, DualPCM, real-HW bus contention, attack-pop) + synthesis. Full findings: workflow wab06bv51.

## Root cause: pitch sag

Two distinct, compounding causes — and the references reconcile cleanly with our VGM data:

(1) STATIC jitter (23%): our output rate IS our loop trip-time, and the loop trip-time is PATH-DEPENDENT. The Timer-A "pacing" is a fiction: the loop's variable fill/drain work overruns the timer period and misses a variable number of ticks (dac-jitter doc rows: N=1020 6kHz/23%; widening N only crushes the rate). The three divergent paths — SndDrv_FillOne real-fill vs ring-full no-op (the `cp 4 / ret c` early-out at line 263-264 skips the entire ~30-cyc read+write), and the SndDrv_Main FILL vs `.drain` branch (line 144-159) — differ by ~20us, and that variance IS the metronome. This is EXACTLY MegaPCM's documented failure: a mere 4-Z80-cycle imbalance between paths was audible at 22kHz (their CHANGES.md). Every reference that has constant pitch (S3K, S1, S2, Flamedriver, MegaPCM, DualPCM) achieves it the same way: every code path through the per-sample loop costs the identical number of Z80 cycles. We have three unbalanced paths, so we have three pitch populations.

(2) UNDER-LOAD sag (9% rate drop + 108% jitter + 483 gaps >1ms, max 6122us): the multi-ms gaps are the Z80 LOOP STALLING on a ROM read while the 68k holds the cartridge bus during a VDP DMA. Hardware research (Kabuto via plutiedev, confirmed on BlastEm at 1.3% off real HW) is decisive: ordinary 68k CPU load adds only a BOUNDED ~3.3-Z80-cycle penalty per ROM-window read — that alone canNOT produce a 6ms stall or a 9% sag. The ONLY mechanism that stalls a Z80 ROM read for thousands of cycles is an active 68k->VDP DMA burst holding the bus for the whole transfer. So the sag is NOT generic "bus contention under load" — it is specifically our SndDrv_FillOne reading ROM (line 266-269 `ld hl,(SND_ROM_PTR) / ld a,(hl)`) DURING a DMA window. Our DRAIN mode was supposed to prevent this but the measurement proves it does not: the drain is armed by a VBlank ISR and gated on a 68k "DMA-done" ack (SND_CTRL_DMA_ACTIVE), but (a) DMA can occur OUTSIDE the VBlank window the ISR assumes (our tile-streaming DMA under SOUND_LOADTEST runs continuously), (b) even in drain mode the fill happens in SndDrv_Main BEFORE the next ISR can re-arm, and (c) the ISR-driven handshake has a race where the loop reads ROM in the gap between DMA-start and drain-arm. Net: ROM reads still land inside DMA windows, each one stalls for the DMA duration, and that stall is inside the sample period -> rate sags and gaps balloon. The references that survive this (MegaPCM, DualPCM) do NOT use a fragile ISR handshake; they make the loop ITSELF self-suspend ROM reads for an entire VBlank-length window driven off the VBlank interrupt, pre-buffered enough to never underrun.

## Root cause: attack pop

It is the LOOP-SEAM step, not a start-snap. I inspected the TEMP blip (data/sound/temp_blip.bin, 2880 bytes): byte[0]=128 ($80, dead center — so the sample START is already click-free), but the LAST byte=137 ($89). SndDrv_FillOne loops the sample by resetting the ROM pointer/length (lines 290-293) with NO endpoint matching, so every loop restart the reconstructed waveform steps from $89 back to $80 — a periodic DC discontinuity at the loop frequency, which reads as a recurring click at the "loudest hit"/attack. Secondary contributor: the SND_REQ_SAMPLE handler writes $2B=$80 (DAC enable) on EVERY play request (SndDrv_PollMailbox lines 180-181) rather than once at init; toggling the $2B DAC-enable edge while the YM sample-and-hold latch holds a stale value snaps the analog output and clicks. (The $2A latch is also never primed to $80 before the first sample, but since blip[0] is already $80 this is currently latent, not the active pop — it would bite a different sample.) All references agree: never toggle $2B per play/loop, keep the stream continuous across loop restarts, and ensure loop endpoints match (start==end, ideally both $80).

## Recommended architecture (MegaPCM 2 model)

Adopt the MegaPCM 2 model: a FREE-RUNNING, EVERY-PATH-EQUAL-COST streaming loop with a page-aligned RAM ring, bounded read-ahead, and a VBlank-long RAM-only drain. Delete YM Timer-A pacing entirely (the loop trip-time IS the sample clock).

LOOP STRUCTURE (one straight-line iteration, di-protected, exactly one ei window):
  SndDrv_Sample:
    di
    ; --- CONSUMER (the $2A write) — fixed cost, reads RING ONLY, never ROM ---
    ld a,(SND_RING_RD) ; l = rd
    ld l,a / ld h,SND_RING_PAGE
    ld a,(hl)                 ; sample byte from RAM ring (7 cyc, NEVER contended)
    ld (ix+0),SND_REG_DAC_DATA ; select $2A  (19)
    ld (ix+1),a                ; -> DAC      (19)
    inc l / ld a,l / ld (SND_RING_RD),a
    ; --- PRODUCER (read-ahead 2 ROM bytes into ring) — slotted AFTER the write ---
    ; page-aligned ring: ldi-style copy, fix the high byte with one ld.
    (read-ahead path:  ldi ; ldi ; ld d,SND_RING_PAGE ; jp po,.bankEdge)
    ei                         ; THE ONLY ei — VBlank IRQ can land ONLY here, between samples
    ; --- read-ahead-OK / lead check ---
    Playback_ChkLead -> jp SndDrv_Sample

THREE SIBLING PATHS, each PADDED TO THE IDENTICAL CYCLE TOTAL (copy MegaPCM's explicit "; Waste NN cycles" technique — pads derived from instruction cycle counts, NOT guessed):
  - NORMAL (2-byte read-ahead): the full-cost reference path.
  - RING-FULL / lead<=guard: skip the two reads but execute an EXACTLY-matching pad (MegaPCM: push af / ld a,nn / nop x4 / pop af / jr = ~53 cyc). Cap read-ahead lead at a fixed small distance so the producer can never run away; the no-op path is then rare AND equal-cost.
  - DRAIN (DMA window, NO ROM): consumer-only + an equal-cost pad (MegaPCM: push bc / inc bc x5 / pop bc / jr = ~56 cyc). All three within 1 cycle of each other.

PACING / ROM-READ PLACEMENT: ROM read STAYS in the loop (read-ahead into the ring), unconditional and constant-position in the NORMAL path — do NOT pivot to a 68k-fed buffer (hardware research + our own idle capture both prove the ROM read is constant-latency under ordinary load). The consumer reads RAM only, so the $2A cadence is decoupled from the bursty producer. NO Timer A. Bake the loop's measured cycle total into a build-time `function` (S3K/S2 pcmLoopCounter pattern) so the rate is computed, self-documenting, and recomputed if the loop body changes — this satisfies our CODING_CONVENTIONS compile-time-math rule.

DMA HANDLING (the real fix for the under-load sag): make the DRAIN a property of the loop driven directly by the VBlank IRQ, NOT a fragile 68k ack handshake. On VBlank RST 38h, switch the loop's read-ahead instructions to the DRAIN (no-ROM) sibling and play purely from the ring for a FIXED, VBlank-outlasting count (MegaPCM plays 144 samples / covers ~8653 cyc NTSC, up to ~20008 PAL; our 256-byte ring covers this — at ~150 cyc/sample only ~57 samples fit in an NTSC VBlank, leaving huge margin). Keep the read-ahead lead pre-filled enough that the drain can never underrun. The 68k must NEVER stopZ80 around DMA (already true — keep it). Drop SND_CTRL_DMA_ACTIVE ack and SND_PLAY_MODE branch-in-main; the drain is self-timed off the IRQ, so there is no per-sample fill/drain branch in the steady state at all (eliminating that jitter cluster).

RING/BUFFER: keep the 256-byte page-aligned ring at $1700. Keep the cached SetBank ($6000 9-bit latch, SND_CUR_BANK no-op check) hoisted out of the hot loop. Bank selection happens once at sample start (bank-aligned samples never re-bank mid-sample).

## Why this over alternatives

Decided on merit for OUR raw-8-bit-PCM streaming engine, not by precedent:

vs CYCLE-COUNTED PER-SAMPLE-ROM (S3K/S1/S2/Flamedriver djnz-pad model): those read ROM in the timed path and survive only because (a) low rates give huge djnz slack that swallows the bounded ~3.3-cyc contention, and (b) the SYSTEM busreq's the Z80 around DMA (S2/S3K stopZ80), which uniformly freezes the Z80 so the work/pad relationship is preserved. We deliberately removed stopZ80 (it freezes the DAC and we want DMA-survival), so the bare djnz-pad model would put a raw ROM read inside DMA windows with no protection — that is precisely our 6ms-stall bug. We'd have to re-add stopZ80 (DAC freezes audibly on heavy frames) OR add DMA survival anyway — at which point we've built MegaPCM. So the pure djnz model is strictly worse for our DMA-survival requirement.

vs PRE-BUFFER (68k fills a RAM buffer, Z80 consumer reads RAM only): tempting but unnecessary and our data disproves the premise. Our idle VGM capture showed constant ROM-read latency, and hardware research confirms ordinary-load contention is bounded+small. The ONLY load hazard is the DMA window, which the VBlank-drain already covers without involving the 68k. A 68k-fed buffer adds 68k CPU cost every frame, a producer/consumer sync problem, and doesn't solve anything the read-ahead ring doesn't already solve. Our own dac-jitter doc already concluded "no 68k-fed-buffer pivot needed."

vs TIMER-A (our current design): empirically a dead end (dac-jitter doc conclusion #2). Timer pacing only works if the loop fits the period; our variable loop overruns and misses ticks, so output==loop speed anyway — we get all the timer complexity and none of the constancy. MegaPCM/DualPCM both abandon the timer for exactly this reason.

The MegaPCM model is the closest to what we already have (page-aligned 256-byte ring, 2:1 catch-up, $8000 window, cached 9-bit SetBank — we independently arrived at its primitives), and it is the ONLY model that solves all THREE problems our doc enumerates: (1) per-sample cycle balance via explicit equal-cost pads, (2) load-independent rate via RAM-only consumer + bounded read-ahead, (3) real DMA survival via a VBlank-long RAM drain with no 68k stop. It's the minimal change from our current code that is provably correct.

## Attack-pop fix

Three independent, cheap fixes (apply all):

1. ENABLE DAC ONCE, NOT PER PLAY. Move the `$2B=$80` write from the SND_REQ_SAMPLE handler (SndDrv_PollMailbox lines 180-181) to SndDrv_Init, issued once. Never toggle $2B per play or per loop. Only write $2B=$00 on a true STOP, and when stopping, first ramp the output down to $80 over a few samples to avoid a stop-click.

2. PRIME THE $2A LATCH TO $80 AT INIT (and keep a continuous DC-center idle stream). After enabling $2B once, write $2A=$80 so the sample-and-hold sits at center before any sample. When idle (no sample), keep feeding $80 to the ring/consumer rather than stopping output (DualPCM's permanent silence-sample idea) — eliminates enable/disable and first-sample edges entirely.

3. FIX THE LOOP SEAM (the actual recurring pop). The TEMP blip ends at $89 and loops back to its $80 start — a step every loop. Regenerate the TEMP blip so it is a click-free loop: start AND end at $80 ($128), with an integer number of waveform cycles so endpoints match. This is a build-time data fix (the blip is explicitly TEMP), the cleanest option, no per-sample cost. For future real samples, author/trim loops so blip[loop_end] ~= blip[loop_start]. On loop restart, the new architecture re-seeds pointers and continues the SAME continuous stream with no DAC re-enable and no gap (MegaPCM PCMLoop_Reload), so there is no enable-edge at the seam either.

Net: fix #3 (loop seam, a data change) is the strongest candidate for the recurring "loudest hit" click and should be done first; #1 and #2 harden against enable-edge and stale-latch pops for real samples.

## Implementation steps

1. Regenerate data/sound/temp_blip.bin as a click-free loop: first byte AND last byte = $80 (128), integer number of waveform cycles so the loop seam has zero step. This is the highest-leverage attack-pop fix and is pure data. Rebuild, capture VGM, confirm the periodic loop-frequency click is gone from the $2A delta stream.
2. Move the $2B=$80 (DAC enable) write out of SndDrv_PollMailbox (lines 180-181) into SndDrv_Init, issued exactly once. Immediately after, prime the latch: write $2A=$80. The sample-request handler no longer touches $2B.
3. Delete the YM Timer-A programming from SndDrv_Init (lines 60-65) and the timer-wait/re-arm logic from SndDrv_Main (lines 125-132). The loop becomes free-running; loop trip-time is the sample clock.
4. Rewrite SndDrv_Main as a single straight-line constant-cost iteration: consumer reads ONE byte from the RAM ring and writes $2A (fixed cost), then read-ahead copies TWO ROM bytes into the page-aligned ring (ldi-style, fix high byte with `ld d,SND_RING_PAGE`), then exactly one `ei`, then a lead check that loops back. The ROM read stays in-loop but feeds the ring; the consumer NEVER reads ROM.
5. Add the two equal-cost sibling paths with explicit cycle-counted pads (copy MegaPCM's '; Waste NN cycles' pattern): (a) RING-FULL/lead<=guard path that skips the two reads but burns the matching ~53 cyc (push af / ld a,nn / nop x4 / pop af / jr); (b) DRAIN path (consumer-only, no ROM) that burns the matching ~56 cyc (push bc / inc bc x5 / pop bc / jr). Verify all three paths are within 1 cycle via emulator_step cycle counting.
6. Cap the read-ahead lead at a fixed small distance (replace the current `cp 4` guard with MegaPCM's sub/sub-N/jp-nc bounded-producer check) so the producer cannot run away and the no-op path stays rare and equal-cost.
7. Replace the ISR-handshake drain with a self-timed VBlank drain: on RST 38h, switch the loop's read-ahead instructions to the DRAIN sibling (self-modifying-code or a mode byte read once per pass at equal cost) and play purely from the ring for a FIXED count that outlasts a full VBlank (>=144 samples / ~8653 cyc NTSC, ~20008 PAL). Then restore read-ahead. Remove the SND_CTRL_DMA_ACTIVE 68k-ack dependency and the SND_PLAY_MODE fill/drain branch in SndDrv_Main.
8. Ensure the ring is pre-filled with enough read-ahead lead before VBlank that the drain can never underrun (lead >= max drain count). Confirm the 256-byte ring covers worst-case VBlank+DMA (it does: ~57 samples fit an NTSC VBlank at ~150 cyc/sample, ring holds 256).
9. Add a build-time `function` (S2/S3K pcmLoopCounter pattern) that computes/documents the effective sample rate from the measured loop cycle total, so the rate is compile-time-derived per CODING_CONVENTIONS and auto-updates if the loop body changes.
10. Keep the cached SetBank ($6000 9-bit latch + SND_CUR_BANK no-op check) hoisted to sample-start only. Confirm the 68k never stopZ80's around DMA (verify no orphaned stops in the 68k VDP/DMA paths).

## Measurement plan

Use the Exodus MCP VGM capture (emulator_vgm_start/stop) + the existing /tmp/vgm_analyze.py $2A-interval histogrammer. For EACH change, capture a SINGLE continuous run (not two run_to_scanline calls — the doc flagged the two-run capture as a suspected artifact source).

STATIC verification (per-sample balance): build, play the blip on the idle harness, capture ~2s, confirm the $2A inter-write histogram is UNIMODAL (target: >99% at one interval, vs the current 91.6%/two-cluster). Cross-check by emulator_step-counting each of the three loop paths and confirming they are within 1 Z80 cycle — do this BEFORE trusting the histogram (the doc's blind pad-tuning failed; count cycles, don't guess pads).

UNDER-LOAD verification (the critical one idle missed): reproduce the heavy-DMA condition with the existing DEBUG SOUND_LOADTEST flag (forces +6px/frame camera scroll -> continuous tile-streaming DMA). Capture a continuous run under forced scroll and compare against the documented LOAD baseline (5430 Hz, 108% jitter, p99=907us, max=6122us, 483 gaps >1ms, 27 >5ms). PASS criteria: (a) mean rate within ~1% of the STATIC rate (no sag), (b) jitter back near the static figure, (c) ZERO gaps >1ms (the multi-ms gaps are the ROM-read-during-DMA stalls; the VBlank drain must eliminate them entirely). Specifically re-run the exact LOAD-interval distribution (p50/p90/p99/max, count of gaps >1ms and >5ms) and require max < ~2x the sample period.

ATTACK-POP verification: capture the $2A value stream across loop restarts; confirm there is no step at the loop seam (consecutive $2A values across the wrap differ by the same small delta as mid-waveform, not a $89->$80 jump) and no $2B toggle appears in the VGM during playback/loop. Listen-test the loudest hit for the click.

Also assert the MegaPCM emulator-fidelity point: BlastEm/Exodus model Z80 bus contention realistically (~1.3% off real HW per MegaPCM calibration), so these Exodus measurements are trustworthy for the DMA-stall behavior — no real-hardware capture required to validate the fix direction.

## Risks

- VBlank-drain coverage: if DMA bursts exceed the drain count (or DMA happens outside the VBlank window the drain assumes), the ring underruns and the sag returns. Mitigate by sizing the drain to outlast worst-case VBlank (>=144 samples) AND confirming the engine's tile-streaming DMA is actually confined to the VBlank handler — our SOUND_LOADTEST scroll DMA may run continuously, in which case drain must be re-armable mid-frame or the read-ahead lead must cover continuous DMA. Measure under SOUND_LOADTEST specifically.
- Equal-cost pad accuracy: MegaPCM proved a 4-cycle imbalance is audible at 22kHz. Our YM writes are ix-indexed (ld (ix+0),n / (ix+1),a = 19+19 cyc) vs MegaPCM's ld (de),a (7 cyc), so our per-iteration cost and pad sizes differ from MegaPCM's literals — the pads MUST be recomputed from OUR instruction cycle counts via emulator_step, not copied verbatim.
- Self-modifying-code drain switch: if the VBlank ISR rewrites loop instructions to toggle drain (DualPCM style), an IRQ landing mid-rewrite or mid-ROM-read can corrupt state. Constrain the ei window to exactly one instruction (between samples) so the IRQ can only land at a safe point, as MegaPCM/DualPCM do.
- Rate is bounded by per-iteration cost: with ix-indexed YM writes our floor is ~150-200 cyc/sample (~18-24kHz ceiling). If real samples need >22kHz we must trim the loop (MegaPCM turbo loop) — likely fine for now but flag it.
- Removing the 68k DMA-done ack (SND_CTRL_DMA_ACTIVE) changes the 68k/Z80 contract; ensure no other 68k code depends on that byte before deleting it.
- Idle DC-center streaming (feeding $80 when idle) keeps the DAC channel always-on, stealing FM6 permanently; confirm FM6 is not needed for music, or only stream $80 idle while a DAC voice is actually allocated.

## Open questions

- Is the engine's tile-streaming / VDP DMA strictly confined to the 68k VBlank handler, or can it run mid-frame (continuous, as SOUND_LOADTEST forces)? This determines whether a single VBlank-triggered drain suffices or the drain must be re-armable / the read-ahead lead must cover non-VBlank DMA. Measure when the actual DMA bursts occur relative to the Z80 VBlank IRQ.
- Final target sample rate for real content (drives the per-iteration cycle budget and whether the ix-indexed YM-write cost forces a turbo/trimmed loop). User-driven once real samples land.
- Should idle output a continuous $80 DC-center stream (permanent DAC-on, click-free, but steals FM6) or fully stop the DAC between samples (frees FM6 for music, but reintroduces enable-edge management)? Depends on whether FM6 is used by the music engine — defer to user / music-sequencing design.
- Loop semantics for real samples: one-shot vs looped is per-sample (SND_LOOP_OFS exists). The seam-match requirement only applies to looped samples; confirm the authoring/tooling pipeline enforces start==end (or seam crossfade) for looped DAC samples.
- Exact pad cycle counts: must be measured against OUR loop body via emulator_step before landing — cannot be finalized from the references' literals due to our different YM-write addressing mode.
