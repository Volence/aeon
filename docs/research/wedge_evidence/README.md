# Sound-driver bus/DMA anomaly evidence (2026-07-02)

Two related findings captured during the sound performance & budget phase. Both live at the
same seam: Z80 activity vs the 68k VInt DMA window, under oracle.

## 1. `hcz2_44s_corruption_baseline.vgm` — the one-shot bank-window corruption

Oracle VGM capture (DEBUG build of master `b024cb6`, HCZ2 id 3 via hotkey UP, no stop pressed).
At t=44.235s (event-tick ≈2232 of 2688, mid-stream, content-ordinary) every Z80 `$8000`-window
read began returning `$FF` permanently: the in-flight drum's ring FILL turned into a solid $FF
slab, and each channel silently ended at its next fetch (`$FF` = MEV_END, no key-off — the
staggered vibrato-write cutoffs at 44.27-44.33s in this capture are the fingerprint). A later
song load stayed silent (header parse read $FF → chcount clamp → 0-channel song) because
`SndDrv_SetBank`'s cache short-circuit never reprogrammed the physical latch — THAT persistence
is fixed (`dcfd4b4`, load-time cache poison). The corrupter itself is unidentified; it did NOT
reproduce on a deterministic re-run (same ROM, same inputs — the song played past its 54.1s
loop), so it is alignment-dependent. Full analysis: DEFERRED_WORK.md "Bank-latch desync
corrupter — unidentified (2026-07-02)".

The packed HCZ2 data was exonerated line-by-line (all 9 channels exactly 2688 ticks, loop
points present, per-channel VGM key-on counts match the blob to ±1 up to the death tick).

## 2. The StopMusic cross-wait wedge (deterministic — no capture needed)

`Sound_StopMusic` during any song (HCZ2, MT; reproduces on unmodified master `b024cb6` and at
multiple frame alignments): the 68k ends up PERMANENTLY stalled on a VDP control-port write
inside `Process_DMA_Critical` (a 210-word plane-buffer DMA shows dma_busy=true forever, FIFO
full), while the Z80 is frozen at `Sfx_StopAll`'s entry (~Z80 `$0FF3`) on a plain RAM
instruction — registers and even the R refresh counter stop advancing. Neither CPU faulted:
it is a cross-wait in the bus arbitration (the 68k-source DMA never completes while the Z80
sits frozen, and vice versa), entered when the Z80's long stop-processing tick (StopAll's
key-off burst) overlaps the VInt DMA-queue drain.

Established by controller debug session 2026-07-02: `Sound_PostByte`'s $2700+stopZ80 bracket
completes cleanly (watched instruction-by-instruction); the mainline survives; the wedge
develops in a later VInt. Whether this is a faithful model of the real-hardware "Z80 vs
68k-DMA" freeze or an oracle arbiter defect is the open question (oracle-source investigation
pending). Reproduction: boot ≥300 frames → UP or A → ~120 frames → START.
