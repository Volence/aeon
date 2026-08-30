# The authored colour bands, on screen (2026-08-30)

**EFFECTS-W1 item 2, the spike.** The owner's question was *"nobody has ever seen one"*.
No bytes moved; this is an answer, not a feature.

## The answer: yes, all three bands reach the screen — and here is why nobody had seen one

`after-three-bands.png` is OJZ Act 1 with `OJZ_BandDemo` installed. `before-no-bands.png`
is the same paused frame with the act's own raster program. `annotated-crop.png` is a 4x
crop of the tree trunk the bands land on hardest, with magenta lines at the authored band
edges — the trunk steps visibly brighter through the three bands.

Measured on frame 186, `s4.debug.bin` crc `2404d825`, assembler sigil `85a5726c`:

| band | rows | authored | pixels it owns | rendering the authored colour |
|---|---|---|---|---|
| 1 | 120-147 | `$0224` | 185 | 173 |
| 2 | 156-183 | `$048C` | 249 | 239 |
| 3 | 192-219 | `$06AE` | 268 | 256 |

**The bands own 1173 pixels of 71680 — 1.64% of the frame.** That is the whole reason they
have never been noticed. A band recolours ONE palette entry (line 2 index 5, the ground
ramp), and in this scene only that fraction of pixels is drawn with it. The mechanism is
not weak; the demo's choice of entry is what makes it near-invisible. Anything meant to
read as staged light wants either an entry the scene uses broadly or several entries at
once.

The ~11 pixels per band still rendering base are the band's first row or two, consistent
with where the arm fires; `band_witness.py`'s build-time arm-chain decode (PIN 5) is what
pins exact transition lines, not this.

## Two instrument traps, both cost real time here

1. **`emulator/pixel_attribution` is authoritative for `cramIndex`, NOT for `rgb`.** Its
   rgb resolves against **live** CRAM at the moment you ask, while `cramIndex` comes from the
   line as it was rendered — so on any frame where a raster program rewrites CRAM mid-frame the
   two fields describe different moments, and nothing in the reply says so. It reported the BASE
   colour for all 702 band pixels while the framebuffer held the band colours. **Read `cramIndex`
   from attribution and the colour from the png.**

   **CONFIRMED FROM ORACLE'S SOURCE, not just inferred from this measurement** (reported to the
   oracle lane, who reached it independently from the other end; verified firsthand here at oracle
   `fcefc04`): `crates/oracle-core/src/render.rs:1897` builds the reply with
   `rgb: self.cram_rgb_state(winner.cram_index, winner.state)` beside
   `cram_index: winner.cram_index`, and `cram_rgb_state` (`:1205`) reads `self.cram()` — the live
   table. Oracle has taken it as a fix rather than a doc note; until it lands, the workaround above
   is the method. Two derivations from opposite ends — a 71,680-pixel sweep against a screenshot,
   and a read of the assignment — which is corroboration rather than echo.
2. **The core's Genesis->RGB is truncating, not rounding.** `$0224` renders `(72,36,36)`,
   not the `(73,36,36)` a `round()` gives. Counting pixels against a hand-written formula
   scored bands 1 and 2 at ZERO and read exactly like "the band does not render". Compare
   against the core's own output on a known entry, never against your own formula.

Reproduce: `python3 tools/band_capture.py s4.debug.bin s4.debug.lst docs/captures/2026-08-30-bands`
Gate (the pass/fail one): `python3 tools/band_witness.py s4.debug.bin s4.debug.lst` — PASS.
