# Spec — VDP Register Shadow: DMA-Path Audit

## Context

We already ship a VDP register shadow at `engine/vdp_init.asm` and the
`setVDPReg` macro that updates the shadow + writes hardware. The shadow
covers regs `$00`–`$12` (per `ENGINE_ARCHITECTURE.md` §1).

While reading the Ristar disassembly we noticed a specific *usage*
pattern around DMA blocks that we should adopt: **before every DMA
transfer, the per-frame VBlank handler restores VDP `$01` (display +
DMA enable) from a RAM cache (`$FFEA46`). Between transfers it
re-reads the shadow and re-toggles bit 4 (DMA enable) cleanly.**
See `ristar_disasm/ANALYSIS.md` "Per-frame DMA pattern" + 
`ristar_disasm/code/disasm.asm` lines 5478–5562.

Why this matters: any code path that writes VDP `$01` directly (to
toggle DMA enable, display enable, VInt enable, etc.) without going
through the shadow will desync the shadow from hardware. On the next
shadow flush, hardware ends up with the *stale* shadow value — at
best you re-disable DMA, at worst you re-enable display mid-DMA and
get visible glitches. Ristar's discipline is "read from `$EA46` shadow
→ modify → write to hardware → write back to shadow."

## Goal

Audit the DMA queue, HBlank dispatcher, section streamer, and any
other VDP `$01`/`$00` writers; ensure every write goes through the
shadow consistently.

## Files in scope

**Read first:**
- `engine/vdp_init.asm` — `VDP_Shadow_Init`, `Flush_VDP_Shadow`
- `engine/dma_queue.asm` — does it touch `$01` directly?
- `engine/hblank.asm` — does it modify any VDP regs without the shadow?
- `engine/level/load_art.asm` — manual DMA pushes from section streamer
- `engine/vblank.asm` — frame VDP setup
- Any other file that contains `move.w #$8X__,` (direct VDP register writes)
- `ristar_disasm/ANALYSIS.md` — "Per-frame DMA pattern" section, plus the
  raw disasm at `code/disasm.asm` lines 5478–5562 for the reference pattern
- `ENGINE_ARCHITECTURE.md` §1 — current shadow design

## Tasks

1. **Audit pass.** Grep `engine/` for any direct write to VDP control port
   that targets register `$00`–`$12` *without* going through `setVDPReg` or
   updating the shadow. Produce a list (file:line, what register, what bit).
2. **Classify each hit.**
   - Hits that should use the shadow → fix to use it.
   - Hits that legitimately need to bypass the shadow (e.g. raw DMA reg
     `$13`–`$17` writes during a DMA push) → leave alone, document why
     in a comment.
3. **DMA queue specifically.** Confirm `Issue_DMA_Queue` does not toggle
   reg `$01` directly. If it does (e.g. to ensure DMA enable is on before
   the transfer), refactor to read the shadow value, OR-in `$10` (DMA
   enable bit), write to hardware, restore from shadow after the transfer.
   The Ristar pattern at `code/disasm.asm:5478-5520` is the reference.
4. **HBlank handlers.** Per-section HInt routines are likely candidates
   for register pokes. Establish a convention: HInt handlers may freely
   write VDP regs *during the active line* but must NOT change the
   shadow. (The shadow represents "settled" frame state, not transient
   raster effects.) Document this in `ENGINE_ARCHITECTURE.md` §1 or §7.
5. **Add a debug invariant** (build-flag-gated, optional): in
   `Flush_VDP_Shadow` (or a debug wrapper), assert that the shadow
   matches a known-good baseline before flushing. Catches accidental
   shadow corruption from buggy handlers.

## Acceptance criteria

- [ ] No direct writes to VDP regs `$00`–`$12` outside of `setVDPReg` or
  the documented exceptions.
- [ ] DMA enable is toggled via the shadow OR documented as transient.
- [ ] HInt handler authoring rules are documented.
- [ ] Build green; ROM-equivalent at hardware level (visible test: still
  boots, title screen still renders cleanly, no flicker).

## Notes

- This is small. Likely 1–2 hours including the audit pass. Call it
  done when the audit list reaches zero open hits.
- Do NOT add a per-DMA-block save/restore *unless* the audit finds a
  current desync. Ristar's pattern is reactive insurance against direct
  writes; if our code never directly writes `$01`, we don't need it.
- If the audit finds an actual current bug (shadow drift), open a
  separate ticket; this audit's purpose is hardening, not bug-finding.
