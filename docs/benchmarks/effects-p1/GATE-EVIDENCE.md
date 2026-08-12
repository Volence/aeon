# Effects P1 — gate evidence (oracle, 2026-08-12)

ROM: `s4.debug.bin` crc=`66ce78de` len=428548, built from
`feat/effects-p1-raster-core` against sigil `9f6b6209` + `feat/effects-p1-registry`.
Content: `OJZ_TestRaster` on OJZ act-1 section 1, `OJZ_TestPal` on section 2.

Method: capture the framebuffer and count pixels whose RGB is **exactly** the
colour the raster program writes — CRAM `$000E` decodes to (238, 0, 0). Counting
"reddish" pixels instead is useless here: OJZ's tree trunks are naturally brown and
swamp the signal (a first pass reported a spurious boundary at row 45). Brightness
means are likewise useless: the canopy/ground art boundary at row 111->112 is a far
larger step than any raster effect.

## Result — the split lands where it was authored

| capture | exact-target rows | row 118 | row 119 | row 120 |
|---|---|---|---|---|
| `gate-latched-wrong-mask.png` | **0..223** | 70 | 57 | 70 |
| `gate-split-at-120.png` | **119..223** | 0 | 1 | 70 |
| `gate-split-midscroll.png` | **119..223** | 0 | 52 | 80 |

Both good captures are **mid-scroll** frames (taken at the instant a sustained
right-hold was released, camera still moving) at two independent camera positions
(240 and 250 frames of scroll), per the standing rule that at-rest frames hide
scroll artifacts.

**Zero above row 118, full effect from row 120.** The authored intent — fire at line
119 so the effect lands on 120 — is confirmed, and with it the whole chain: sparse
HInt dispatch, the build-time arm words, the two priming records, and `BIAS = 1`.

## The A/B that isolates the palette re-assert

`gate-latched-wrong-mask.png` is the same ROM with one word different:
`pal_dirty_mask` naming palette line **0** while the CRAM op writes line **2**.
Nothing restores line 2, so the write latches and the target colour appears on
**every** row (0..223) instead of below the split. This is the direct proof that the
per-frame `pal_dirty_mask` re-assert is what makes a mid-frame CRAM write transient —
and a live trap for authors: **the mask must name the line the ops write.**

## Residual: row 119 is partially affected, and by a varying amount

1 px in one capture, 52 in the other. This is the CRAM write landing *during* line
119's active display — single-ported CRAM shows the value being written at the pixel
being drawn (survey Ruling 2b), so pixels drawn after the write on that line already
carry the new colour, and how many depends on where in the line the write lands.
Not a scheduling error (the fire line is right); a write-position artifact.

For a pixel-clean boundary, Phase 2's options are the documented ones: fire one line
earlier and accept the effect starting a line high, or push the write into blanking
with the S3K cycle-counted `dbf` approach (`sonic3k.asm:1018`, `:1038-1039`). Left
open deliberately — the water cluster is where a clean boundary actually matters.

## Also verified

- **`sec_pal` (per-section palettes, previously descriptor-only).** Crossing into
  section 2 snaps CRAM to `OJZ_TestPal` (read back: the garish blue ramp, indices
  1-15 matching the generated values); crossing back restores. Before the palette
  contract was fixed, this consumer clobbered CRAM line 0 and rendered the level in
  wrong colours — that failure and its fix are the reason `OJZ_FullPalette` exists.
- **`sec_raster_table`.** `Raster_Program` reads `$00011EF2` = `OJZ_TestRaster` while
  the camera is in section 2, i.e. the program installed on entry to section 1 and
  correctly *persisted* across a NULL-`sec_raster_table` neighbour ("keep current").
- **Lag frames.** The effect survives sustained scrolling, which exercises the
  `VInt_Lag` re-arm mirror; a missing mirror would park the counter and kill the
  effect until the next full frame.

## NOT verified — stated plainly

**The Shadow/Highlight half of the gate produced no visible dimming.** S/H only
shadows *low-priority* pixels and OJZ's art is high-priority, so there is nothing for
it to dim. The `OP_SET_REG` op demonstrably *executes* — it precedes the CRAM op in
the same fire record, so a mis-parse would have desynced the CRAM command and we
would see garbage rather than a clean boundary at 120 — but its visual effect is
unobservable with this content. Reading VDP register `$0C` back would settle it
directly; oracle exposes CRAM/VRAM/VSRAM and CPU registers, not VDP registers.

Deferred to Phase 2, where the water cluster supplies low-priority content that makes
S/H observable by construction. Do not record S/H as visually proven on P1.

---

## Re-verification after the rebase onto master (character-dispatch + Knuckles)

ROM: `s4.debug.bin` crc=`a3f4f13e` len=707280 (the ROM grew from 428 KB — the
character-art tail exile), built against sigil master `14049a9c` (chain 102).

**The raster split is byte-identical to the pre-rebase result.** Same method, same
camera position (150 start + 240 right): exact-target rows 119..223, zero above row
118, row 119 = 52, row 120 = 80. A pixel-for-pixel compare of the two framebuffers
is **71680/71680 identical (100%)** — the rebase over 67+ commits of character work
changed nothing observable about the raster path.

## The character-palette invariant, verified directly

The rebase surfaced that **CRAM line 0 is the CHARACTER line**, owned by
`Player_ApplyCharacter` via `CharacterDef.cd_palette`. The original P1 consumer
copied a full 128-byte image including line 0 on every boundary crossing, which
would have repainted the active character mid-act (Knuckles reverting to Sonic's
colours at the first boundary). Fixed: `sec_pal` is 96 bytes -> CRAM lines 1-3, and
`Palette_Dirty` gets `%1110`, never bit 0.

Tested by sentinel rather than by driving the character hotkey, which isolates the
mechanism instead of depending on debug-mode state:

1. Wrote `$0EEE` into all 16 entries of `Palette_Buffer` line 0 (standing in for a
   character having set its own palette).
2. Scrolled right across the boundary into section 2, which carries `OJZ_TestPal`.
3. Read back at Camera_X = `$1115` (section 2):
   - lines 1-3 = `0000 0020 0040 0060 0200 0220 0240 0460 ...` — the section palette
     loaded, so the consumer definitely ran
   - line 0 entries 1-15 = `$0EEE` — **the sentinel survived untouched**

Entry 0 alone read `$0E00`, written by `ojz_scroll_test`'s own per-frame backdrop
poke, not by the section consumer. Before the fix, all 16 entries would have been
overwritten. This is the invariant the Knuckles palette round-trip depends on.
