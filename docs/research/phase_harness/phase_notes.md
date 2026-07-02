- Quality review T2 minor #3 (pre-existing, for T12 DEFERRED_WORK): under SFX override, bare-note/NOTE_DUR paths skip the sc_base_freq latch (Seq_HookNoteOn ret nz) so a note change DURING a steal restores the pre-steal pitch; NOTE_RAW pre-gate latch is the model fix. Comment at sound_sfx.asm:1013-1017 oversells.

## StopMusic 68k wedge — diagnosed 2026-07-02 (controller emulator session)
- DETERMINISTIC + PRE-EXISTING (reproduces on unmodified master b024cb6): any song (HCZ2, MT) → Sound_StopMusic (START hotkey) → 68k PERMANENTLY stalled on a VDP control-port write inside the VInt plane/DMA-queue drain (PC frozen, single-step no-ops; not the error handler; screen frozen normal).
- Machine state at wedge: VDP dma_busy=TRUE forever on a 210-word 68k-source DMA (source = plane buffer $FF86E6-region), FIFO full; SR=$2600 (in VInt); SP $FFFFFEB2 identical across repros; Z80 HEALTHY (idle loop ticking, r advancing).
- NOT: Timer-A (alive), Z80 crash, phase alignment (reproduces at +120 and +121 frame offsets), Task 2/3 changes (master wedges).
- Contrast: Sound_PlayMusic posts through the IDENTICAL $2700+stopZ80 bracket and never wedges → differentiator is the Z80's STOP-side processing inside the tick (Sequencer_StopAll burst? $27 write? post-stop idle SetBank cadence?) racing the VInt DMA window, OR an oracle VDP/arbiter emulation defect triggered by that ordering.
- 44.2s HCZ2 corruption plausibly the same collision seam (Z80 window/bus activity vs active 68k-source DMA), rare-alignment variant.
- Next: bounded dynamic session — breakpoint Sound_StopMusic, step the wedge onset on both CPUs + VDP status; then fix task.
- Baseline-capture caveat: Task-1 ours_baseline.vgm was captured WITHOUT any stop → unaffected.
- Quality review T5 minor #2 (pre-existing, for T12 DEFERRED sweep): Seq_Op_RegWrite guards $2A/$2B/$24-$27 but NOT $28 — an authored REGWRITE to $28 can desync chip key state from SCF_KEYED (which the chokepoint bit-test relies on). ~4-6 B to extend the guard.
