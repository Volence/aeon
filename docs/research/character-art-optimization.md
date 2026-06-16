# Character Art Optimization — Research (2026-06-15)

Research into saving ROM / VRAM / DMA for character sprite art. Five parallel
streams: Sonic-lineage disasms (S.C.E./S3K/sonic_hack), Treasure/action disasms
(Gunstar/Alien Soldier/Batman/Vectorman/TF4), Ristar, modern/online (SGDK,
SpritesMind, plutiedev, homebrew), and an empirical benchmark on our real data.

## Baseline & the core trade-off

Current: character art is **uncompressed, contiguous, ~122 KB/char**, DPLC streams
only the current frame (~29 tiles max, 928 B) into a 32-tile VRAM window per frame
change. **VRAM is already near-optimal** (only the live frame is resident). **DMA is
never the bottleneck** (928 B « the ~7,524 B/frame VBlank DMA budget). The cost is
**ROM**, and the only knob that trades it is **CPU decompression**.

## Industry consensus (all reference disasms)

Uncompressed tiles + DPLC (or frame-scoped DMA) is the **standard** — S3K, S.C.E.,
sonic_hack, Gunstar, Vectorman, TF4, Batman, Ristar all store sprite art raw and DMA
direct from ROM. **Only Alien Soldier compresses sprites** (a custom 4-mode flag-byte
RLE, decompressed to a RAM buffer before DMA). So compressing character art goes
*against* 1990s consensus — but that consensus predates ZX0/LZ4W, and the old
rejection here was specifically vs **UFTC** (0.82–0.86 ratio, weak). Modern
compressors change the math.

## Empirical numbers (measured on our real Sonic art)

Tools present: `tools/bin/salvador` (ZX0 encoder) + `engine/zx0_decompress.asm`
(88-byte ZX0 68k depacker). S4LZ also present (32 KB window → per-frame only).

**ROM size by strategy (Sonic, from 122,272 B current):**
| Strategy | Size | Saved | CPU cost |
|---|---|---|---|
| Uncompressed contiguous (current) | 122.3 KB | — | none |
| **Dedup pool** (drop contiguity dup) | ~96.3 KB | **−21%** | **none** |
| Dedup + flip-equivalent | ~94.1 KB | −23% | none (flip bits) |
| **Per-frame ZX0 streaming** (each frame its own blob) | ~70.8 KB | **−42%** | active-frame decompress |
| Whole-sheet ZX0 | ~47.5 KB | −61% | *can't fit decompressed in 64 KB RAM* |

- Every frame compresses with ZX0 (worst 0.74, avg **0.58**, best 0.37) — no frame expands.
- Flip-twins in this art are negligible (**36 tiles**, ~1 KB) — flip-dedup not worth its complexity *here*.
- Contiguity costs +11.6% vs source, +25% vs a fully-deduped pool (shared tiles get physically copied).

**Decompression budget (the gate):** frame ≈ 127,833 cyc; VBlank ≈ 9,758 cyc.
- **ZX0** ≈ 20–25 cyc/byte → worst 928 B frame ≈ **18.5k cyc ≈ 14.5% of a full frame, ~190% of VBlank**.
- **LZ4W** ≈ ~10 cyc/byte (600–950 KB/s, SGDK/BigMessOWires) → worst frame ≈ **9.3k cyc ≈ 7% of frame, ~95% of VBlank**.
- **Conclusion: per-frame decompress does NOT fit in VBlank — it must run in the active frame (main loop) before queuing the DMA.** It only costs this on *frame-change* frames (every ~5–8 frames at normal anim speed), not every frame. ZX0 ≈ 8.6% avg / 14.5% worst; LZ4W ~half that for ~10% worse ratio.
- Whole-sheet decompress-to-RAM is a non-starter: 122 KB doesn't fit in 64 KB RAM, and even the 47 KB compressed bank takes ~19 frames to expand. A *moveset subset* (~15–20 KB) to RAM is tractable but complex.

## Ranked levers

1. **Dedup pool (drop contiguity duplication)** — ~21% ROM, **zero CPU**, low risk. The
   contiguity that bought "1 DMA entry/frame" is already partly moot (the 16-tile fix
   forces multi-entry frames anyway). Build-tool change to `dplc_layout.py`. **Do this regardless.**
2. **Per-frame ZX0 streaming** — ~42% ROM. Decompress each frame's blob to a 928-B
   staging buffer in the active frame, then DMA. Real cost must be measured on hardware
   (the 8–14% estimate). ZX0 tool + depacker already in-engine. Highest ROM lever.
3. **Delta-DPLC (NOVEL — no shipped Genesis precedent found)** — only DMA the tiles that
   *changed* vs the previous frame. Build-tool diffs tile pixels across consecutive
   frames, emits a per-transition tile list. Sonic's torso is static across run frames →
   could cut per-frame DMA from 29 to ~5–15 tiles, and shrink ROM. Saves DMA *and* ROM,
   no decompress CPU. Build-tool experiment; runtime is trivial. Flagged high-interest by
   the web stream.
4. **LZ4W as an alternative to ZX0** for #2 — ~2× faster decompress (fits closer to budget),
   ~10% worse ratio. Not in-engine yet (would need to port the depacker). Measure vs ZX0.

## Orthogonal (correctness / cheap wins, not "space" experiments)

- **128 KB DMA-boundary split** — the VDP wraps DMA source within a 128 KB block →
  garbage if a transfer crosses one. S3K/S.C.E. both split. Our `QueueDMATransfer`
  doesn't yet. **Production blocker** once art blobs get large; surfaced independently.
- **DMA per-frame byte-budget enforcement** (Vectorman: cap ~2,880 B/frame, drop overflow) —
  cheap VBlank-overrun guard. High value, low cost.
- **Pre-computed SAT tile word / `dmaSource()` pre-division** (Gunstar/S.C.E.) — a few
  cycles/sprite in the hot path.
- **Art-frame-ID decoupled from anim-frame** (Ristar `SST+$60`) — lets multiple anim
  frames share one art load; we already skip DMA on unchanged `mapping_frame`, so this is
  a minor extension.
- **Form-via-palette reuse** (S3K Super Sonic: same art, different CRAM line) — free, for later.

## Recommended experiment matrix (before/after on real data)

Measure each variant's: ROM bytes/char, decompress CPU per frame-change (emulator
profiler / `Lag_Frame_Count`), DMA bytes/frame.

- **A. Dedup pool** (free ~21%) — baseline improvement, low risk.
- **B. Per-frame ZX0 streaming** (~42%) — measure real active-frame CPU on hardware.
- **C. Delta-DPLC** (novel) — measure ROM + DMA reduction and build/runtime complexity.
- **Combos**: A+B (dedup then compress), A+C (dedup then delta), B+C if compatible.

VRAM is already optimal, so none of these touch the 32-tile window (except Delta-DPLC
reduces what's re-uploaded into it). This is purely a **ROM ⇄ CPU** trade; the matrix
tells us which points on that curve are worth shipping.

---

## RESOLVED — measured results (2026-06-16)

All measured first-hand on the real Sonic art and on-hardware via the Exodus
profiler (viewer forced to the RUN animation so DPLC/decompress fires; same scene
for before/after). The throwaway experiment tools (`gen_sonic_zx0.py`, `lz4w.py`)
were deleted after capturing these — the numbers below are the record.

**Note:** two "orthogonal" items above turned out to be ALREADY IN THE ENGINE —
the 128 KB DMA-boundary split (in `QueueDMATransfer`) and the per-frame DMA
byte-budget (`DMA_Budget_Default`/`DMA_Budget_Remaining`). Not gaps.

**Frame baseline (this OJZ scroll scene, 128k-cycle frame):** ~58% idle slack
(`VSync_Wait` ≈ 74k cyc). The whole player art pipeline (`Perform_DPLC` +
`AnimateSprite` + `Player_Animate`) is ~1.3k cyc/frame — trivial. **The dominant
cost is the parallax scroll (`Parallax_Update` + `Parallax_Fill_PerLine` ≈ 47k cyc,
35% of the frame).** If CPU headroom is ever needed, optimize parallax, not the player.

**A — Dedup pool: SHIPPED.** 122 → 97.5 KB (−20%), provably byte-identical tile
loads (so rendering unchanged), zero CPU, DPLC entries/frame 1.5 → 3.3 (same bytes).
`tools/dedup_art.py` (committed). This undoes our own contiguity inflation and drops
below the 110 KB source.

**B — Per-frame ZX0 streaming: MEASURED, REJECTED.** ROM −42% (71 KB) and it renders
correctly, BUT `ZX0_Decompress` measured **~45,870 cyc per fire-frame** (~20-tile run
frame) = **~75 cyc/byte — ~3× the 18-23k estimate.** Worst-case 29-tile frame ≈ 65-70k.
Fire-frame budget use ~76% (worst-case ~94%, ~3% margin). Fits this scene with no
dropped frames, but margins are thin and a busier scene risks lag spikes. Confirms the
`ZX0_Decompress` header's "never call per-frame" and the research's "ZX0 = load-time only."

**LZ4-class (the faster alternative): MEASURED, REJECTED on ratio.** A from-scratch
LZ4W-style word-granular codec AND real `lz4 -9` (byte-granular, strong) both compress
Sonic's **per-frame** tile art to only **~78%** — barely better than free dedup (~80%),
far worse than ZX0 (57%). Per-frame blobs are small (≤928 B) and independent, so LZ4's
simple matcher finds little; only ZX0's optimal-parse extracts more (at decode cost).
**The literature's "45-53% LZ4W" was on larger/redundant tilesets, not small character
frames.** So the fast codecs that fit per-frame give no ROM win over free dedup.

**C — Delta-DPLC (only re-upload changed tiles): MEASURED, REJECTED.** 0% benefit on
the walk cycle — every position's tile is completely different frame-to-frame (the whole
sprite redraws), so nothing is stable to skip. The web stream's "10-30%, novel" was
speculation; measured = dead for Sonic.

### Verdict
**No per-frame compression sweet spot for this art:** good ratio (ZX0) is too slow,
fast (LZ4-class) is no better than free dedup. **Dedup shipped; compression dropped.**
The only scheme that beats dedup is whole-sheet ZX0 (47 KB, −61%) — but 122 KB won't fit
decompressed in 64 KB RAM, so it'd need a load-time "decompress current moveset to RAM"
architecture (bigger change, load-time only, parked).
