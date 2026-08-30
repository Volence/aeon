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

   **THIS IS DELIBERATE AND DOCUMENTED — and the workaround above is the PRESCRIBED PATH, not a
   workaround** (established 2026-08-30 by the oracle lane, who reproduced it independently on a
   different ROM with a different instrument, then read the method's own contract). Aether
   `protocol.md` §11.3 says a server answers this method by resolving the scanline from live VDP
   state and **MUST NOT read a framebuffer**, and about this exact disagreement: *"This is not a
   defect in either method and a server MUST NOT try to paper over it; a client that needs the two
   to agree needs a per-scanline capability — `emulator/scanlines`."* So reading `cramIndex` from
   attribution and the colour from the raster is what the contract asks for. It is booked as
   F-SCANLINE-INDEX.

   **What IS broken is that nothing in the reply says any of this**, which is the whole cost: the
   two fields disagree silently inside one object, and a caller with one instrument cannot tell.
   Oracle is drafting a contract change to name which moment each answer belongs to — always true,
   rather than a heuristic that tries to detect mid-frame CRAM writes, which would be wrong in both
   directions — and to point a caller at `emulator/scanlines` rather than merely flagging the
   hazard. They have landed an anti-fix pin asserting `rgb` follows LIVE CRAM, whose recorded
   mutation is the framebuffer read, because they built that fix, got a green suite, and reverted
   it on reading the contract.

   *Correction to this file's earlier text, which said Oracle "has taken it as a fix". That was my
   summary of their first lean and it was superseded within the hour. The mechanism I measured is
   real and the numbers below stand; the conclusion that it was a defect to be fixed was wrong.*

2. **The core's Genesis->RGB is truncating, not rounding.** `$0224` renders `(72,36,36)`,
   not the `(73,36,36)` a `round()` gives. Counting pixels against a hand-written formula
   scored bands 1 and 2 at ZERO and read exactly like "the band does not render". Compare
   against the core's own output on a known entry, never against your own formula.

Reproduce: `python3 tools/band_capture.py s4.debug.bin s4.debug.lst docs/captures/2026-08-30-bands`
Gate (the pass/fail one): `python3 tools/band_witness.py s4.debug.bin s4.debug.lst` — PASS.
