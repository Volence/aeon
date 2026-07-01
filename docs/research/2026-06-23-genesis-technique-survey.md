<!--
Research artifact. Produced 2026-06-23 by an 18-agent survey workflow
(3 scout/ground + 7 domain-research + 7 skeptic-map + 1 synthesis).
Verified against codebase before saving:
  - CODING_CONVENTIONS.md:258 SMC "is safe" claim (no prefetch-FIFO caveat) — CONFIRMED
  - CODING_CONVENTIONS.md:215,296 asr.w with no round-toward-minus-inf caveat — CONFIRMED
  - engine/buffers.asm:71 fixed dmaLength(640) SAT DMA + engine/objects/sprites.asm:387
    Sprites_Rendered computed-but-unused for transfer length — CONFIRMED
This is a CANDIDATE survey, not a directive. Per user: do not treat any single
external source as a standard to follow. Locked decisions (S4LZ+ZX0 compression,
Flamedriver sound driver, graph-colored VRAM pool, continuous section streaming)
are respected throughout.
-->

# Genesis Homebrew / Demoscene / Sonic-Hack Technique Survey

*For the Sonic 4 engine (s4_engine). Date: 2026-06-23. Skeptical by default; locked decisions respected. Sources cited inline.*

## 1. TL;DR — worth-taking ideas, ranked

1. **Echo's SFX channel-lock + per-channel BGM state save/restore** is the single best *idea* here, and it directly de-risks our blocked Phase 5 SFX work and the audited "SFX-steal clobbers SCF_KEYED / silence gap" bug. Borrow the model, not the driver. ([Echo `sfx.z80`](https://github.com/sikthehedgehog/Echo))
2. **Doc-fix: CODING_CONVENTIONS line 258 is wrong about SMC.** It says self-modifying code is unconditionally safe ("no instruction cache"). The 68000 has a 2-word prefetch FIFO; patching an immediate within 2 words downstream executes stale bytes. No live bug today, but the doc licenses a future silent-corruption class. Highest leverage-per-effort item in the whole survey. (68k-z80-microopt)
3. **Two-channel software DAC mixer** (drum + SFX summed to FM6, additive-with-scale-LUT) so drums keep playing under DAC SFX — the headline Phase 2 deliverable. Adopt the *design* (Clone Driver v2 / Dual PCM), re-derive our 400-cycle balance, keep our flag-bracket DMA survival. ([Clone Driver v2 / Sik dual-PCM writeup](https://gendev.spritesmind.net/forum/viewtopic.php?t=1606))
4. **Size the SAT DMA to `(Sprites_Rendered+1)*8`** instead of the fixed 640 bytes. We already compute the count but never read it (sprites.asm:387; buffers.asm:71). Reclaims up to ~600 VBlank DMA bytes/frame — real headroom for the ~76% sustained-max-diagonal lag case. (rendering-streaming)
5. **PollPCM cooperative-scheduling pattern** from Echo (a cheap DAC-feed poll woven through every long Z80 code path) hardens DAC cadence and is the clean answer to the audited "one-shot DAC never stops" class. ([Echo `pcm.z80` / `main.z80`](https://github.com/sikthehedgehog/Echo))
6. **MDSDRV's per-frame fnum-accumulator + 256-step-per-semitone grid** is the right implementation model for the portamento we've *already* scoped (seams `sc_porta_incr`/`sc_porta_accum` exist but are unrendered). Not new, but it's the concrete pattern. ([MDSDRV docs](https://gdri.smspower.org/wiki/index.php/Mega_Drive/Genesis_Sound_Engine_List))
7. **Build-time 128KB-straddle assert** on streamed art blobs (the runtime split already ships in dma_queue.asm:70-120; the *build*-time guard does not). Cheap insurance, fold into the windowed-art-streamer plan. (compression-data / 68k-z80-microopt)
8. **`asr` on signed values rounds toward −∞** — a one-line caveat missing from CODING_CONVENTIONS' shift-add section. Prevents a latent sign-bug class in future physics/camera division. (68k-z80-microopt)

Everything below #8 is either already-have, parked, or rejected.

## 2. The two you flagged

**s1disasm commit e393c44 ("Dynamic collision shapes example") — DO NOT ADOPT.** It routes the three fixed collision-data labels (`AngleMap`, `CollArray1/2`) through a new zone-indexed pointer table (`_physFindColTbl`: `move.b v_zone; lsl #2; move.l (a2,d0.w),a2`). As shipped, all seven zone slots point at the same label — it is an explicit *no-op example*, scaffolding for a future hacker. Our engine already solves the underlying goal (collision varying by context) *more cleanly and at finer granularity*: a single per-**placement** byte baked into block data by `collision_pipeline.py`, indexing shared `HeightMaps`/`HeightMapsRot`/`AngleTable`/`SolidityTable`, with **zero runtime indirection** (the byte *is* the collision ID; `(type*16)+(x&0xF)` single lookup). The commit adds ~10-14 cycles of `v_zone`-read + shift + indexed load + bsr/rts on *every* floor/wall sample to buy per-zone granularity we already subsume at per-placement for free. It also carries a probable control-flow defect in `ConvertCollisionArray` (the second array's conversion path looks broken — the "example" caveat is apt) and triggered a `bsr.s`→`bsr.w` widening because the insertion blew the ±128-byte short-branch range. The only nugget is the generic "reference a context-indexed table, not a fixed global" pattern — which we already apply via per-section palettes/type-tables/the deferred physics-modifier table. **Verdict: confirmation our finer-grained build-time-baked collision is the better-of-class choice, plus a reminder of the short-branch hazard our `.s/.w/.l` conventions + s4lint already mitigate. No action.** ([commit](https://github.com/sonicretro/s1disasm/commit/e393c44f91d7a663e44f7c564dac445c32d4b593))

**Echo sound driver — MINE FOR IDEAS, DO NOT PORT.** Echo is a fully-autonomous Z80 driver (68k queues high-level commands; Z80 owns YM2612 + PSG + DAC). Its headline tech does **not** beat us where it counts: PCM is **single-channel at fixed ~10.65 kHz with FM6 sacrificed** — no better than SMPS, worse than our DAC-powerhouse roadmap, and far worse than XGM's 4-ch software mix ([xgm.txt](https://github.com/Stephane-D/SGDK/blob/master/bin/xgm.txt)). Switching would mean abandoning our SMPS-derived migrated corpus and re-authoring everything as ESF/EIF/EEF/EWF with only an XM importer ([xm2esf](https://github.com/sikthehedgehog/Echo)) — a large regression for zero musical gain, against our locked from-scratch Z80 driver. But Echo is an excellent *source of format/scheduling/SFX ideas*, which is exactly the brief. Borrow into Flamedriver: (1) **SFX channel-lock + per-channel BGM save/restore** — the cleanest known answer to "SFX over music without the song losing its place" ([`sfx.z80`](https://github.com/sikthehedgehog/Echo)); (2) **PollPCM cooperative poll** ([`pcm.z80`](https://github.com/sikthehedgehog/Echo)); (3) the **event-stream-as-API** concept (a `PlayDirect`-style 12-byte inject buffer using our own command vocabulary) for adaptive audio; plus cheap wins — **fixed-size build-time-validated instrument records** ("reserved bits must be zero" → branchless register writes, [eif.txt](https://raw.githubusercontent.com/sikthehedgehog/Echo/master/doc/eif.txt)) and **per-tick PSG envelopes carrying an embedded pitch-shift nibble** for free vibrato ([eef.txt](https://raw.githubusercontent.com/sikthehedgehog/Echo/master/doc/eef.txt)). The dual-slot 68k mailbox is interesting but our contract already works — reference-only. **Verdict: keep Flamedriver; harvest the SFX-restore model, the PollPCM pattern, and the inject-buffer idea.**

## 3. Adopt-candidates (verified real wins)

### Audio

**Two-channel software DAC mixer (Phase 2).** *What it is:* sum N=2 8-bit DAC streams into FM6 via per-channel log-volume VLUTs, additive-with-clamp/scale ([Clone Driver v2 / Sik](https://gendev.spritesmind.net/forum/viewtopic.php?t=1606)). *What we do now:* single-channel DMA-survival DAC, cycle-balanced FILL==SKIP==DRAIN==400 cyc (~8948 Hz); a DAC SFX today kills the drum track. *Payoff:* **high game-feel** — drums survive every jump/ring SFX. *Effort/risk:* medium-high. The hard part is re-deriving the per-sample cycle balance for a 2-stream loop (extra ROM read + add + clamp), which *will* drop the effective rate — our ~8.9 kHz already implies tight headroom, so 4 ch is **not** a free target (Stef: 4 ch ≈ 14 kHz ≈ 70% Z80 — and that's a tighter inner loop than ours). Additive 8+8 needs a scale LUT (bit-depth loss otherwise). *Arch fit:* clean — our own Z80 code, already the locked Phase-2 plan, 68k cost stays one mailbox byte. **Keep our flag-bracket DMA survival; do NOT import Dual PCM's pre-buffer heuristic — ours is better.** Start at exactly 2 channels, measure achieved rate via vgm2wav before claiming a count.

**Portamento via MDSDRV accumulator model (Task 7).** *What it is:* per-frame fnum accumulator on a 256-step-per-semitone grid, add-incr-per-frame ([MDSDRV](https://gdri.smspower.org/wiki/index.php/Mega_Drive/Genesis_Sound_Engine_List)). *What we do now:* `sc_porta_incr`/`sc_porta_accum` declared but "NOT rendered yet" (sound_sequencer.asm). *Payoff:* closes a known music-fidelity gap (deep-audit item E). *Effort/risk:* low-medium, de-risked — seams already exist; this is a scoped task, not new architecture. *Arch fit:* native (matches the existing `ModUpdate` per-frame model).

**PollPCM cooperative poll + Echo SFX save/restore (Phase 5).** Covered in §2. *Payoff:* hardens DAC cadence (fixes "one-shot DAC never stops") and gives the correct SFX-over-music model. *Effort/risk:* low-medium; both integrate as our own Z80 code with no architecture change. *Arch fit:* clean against the locked from-scratch driver.

### Rendering / VDP pipeline

**Variable-length SAT DMA.** *What it is:* DMA only `(Sprites_Rendered+1)*8` bytes, not a fixed 640 ([Vectorman-style used-portion DMA](#)). *What we do now:* RAM-shadow SAT, exact-bbox cull, per-band limit tracking, correct link-0 terminator (sprites.asm:387) — but buffers.asm:71 DMAs all 80 entries every dirty frame, ignoring the count we already compute. *Payoff:* low-moderate; reclaims up to ~600 DMA bytes/frame (~8% of the ~7.5 KB VBlank budget) in light-sprite scenes — directly helps the VBlank-bound max-diagonal lag case (SAT shares the Critical queue with plane drain + HScroll). *Effort/risk:* **low/low** — one length computation from a maintained counter. Round up by one entry to include the terminator; keep the length even. *Arch fit:* perfect — aligns with the VBlank-bound streaming budget. *Note: this is NOT a correctness fix; the link-0 terminator already stops the VDP walk. It is purely reclaimed bandwidth.*

### Tooling / conventions (documentation corrections — trivial, high-leverage)

**Fix the SMC paragraph (CODING_CONVENTIONS line 258).** Rewrite to: *"SMC is safe only if the patched word is ≥2 words downstream of the patching instruction, OR a taken branch / RTS / interrupt separates the write from the read (the 68000 has no instruction cache but a 2-word IRD+IRC prefetch FIFO)."* No live bug (grep found no patch-next-instruction pattern), but the current wording would license a real intermittent corruption the first time someone patches a DPLC-base or plane-fill-base immediate inline. *Effort/risk: trivial / none.*

**Add the signed-`asr` caveat.** One line in the shift-add section: `asr` rounds toward −∞ (`-1 asr 1 = -1`), so it is *not* a divide-toward-zero for signed velocity/position. *Effort/risk: trivial / none.*

**Build-time 128KB-straddle assert on streamed art blobs.** The runtime split already ships (dma_queue.asm:70-120); add a `MOMPASS>1` assert in the static-DMA macro + a layout assert on page blobs so the largest transfers avoid the ~150-cycle split path and a data-layout regression is caught at assembly time. *Payoff:* small (belt-and-suspenders — correctness already guaranteed). *Effort/risk: low/low, but premature standalone.* **Bind it to the windowed-art-streamer plan, not now.** Also: update the stale `dma-queue-audit.md` ("128KB safety: deferred") to mark the runtime split SHIPPED.

## 4. Interesting-but-not-now (parked, one-line reason)

- **512-color static image (16 CRAM writes/line during display-disabled HBlank)** ([Titan Overdrive](#)) — eats the whole 68000 per active line; title/cutscene set-piece only, never gameplay; our 3-colors/line HInt gradient is the gameplay subset.
- **DMA-streaming CRAM during active display ("blast processing")** — static-screen-only, monopolizes the channel streaming needs; file the DRAM-refresh-window beam-lock primitive as a curiosity.
- **V30↔V28 vertical-border-opening (+19 NTSC lines)** ([Kabuto](#)) — title/intro only; **WARN in §7.7**: engaging it can drop the VBlank flag/VINT while HINT keeps firing — a real frame-sync footgun.
- **Sprite scaling via pre-scaled tiers + slice repositioning** — building ahead of need; revisit when a boss/special-stage actually needs zoom (slice-via-link-field+X+table fits our mapping format and no-mulu rule).
- **Sprite masking (X=0) as a lightweight overlay clip** — the substrate ships (sprites.asm:616 `InsertSpriteMasks`); the window plane covers our known HUD cases more cleanly; keep as a fallback.
- **4-bit DPCM for low-fi SFX** ([GEMS](#)) — ~half the sample ROM; fold a per-sample PCM/DPCM format flag into the Phase-2 mixer, don't retrofit the 8-bit path.
- **Clone Driver v2 mid-sample bank-crossing** — latent constraint, not a current bug; design each Phase-2 DAC stream to carry its own window ptr + bank id + boundary check, cost the cross into the per-sample budget.
- **Per-channel half-rate DAC flag** ([XGM2](#)) — minor ROM/CPU saver; a Phase-2 mixer knob, not a format change.
- **ZX0 turbo/fast variant ladder** ([Marty/ZX0 68k decoders](#)) — 21-28% faster decode, format-identical drop-in, but ZX0 is load-time-only today so the speedup is invisible; pull in only if a windowed art-residency streamer puts ZX0 on a near-frame budget.
- **EDGE_WRAP_V / floating-origin vertical wrap** ([S&K loopback](#)) — deferred by design; record the **S3K above-camera Y-underflow glitch** as the canonical failure mode for §4.11 (camera-aware clamp + atomic uniform shift).
- **Tagged-source editor schema (LUMINARY/Beehive)** — genuine latent weakness (ObjDef field order duplicated in .asm + Python), but `ojz_strip_gen.py` is daemon-watched and ObjDef is LOCKED/stable; park for the §8 build-system phase, derive schema from the .asm struct then.
- **Cycle-accurate Z80 simulator (Mega PCM 2)** — our hand-balance + vgm2wav already meets the build-time-validation bar; large tooling spend for marginal extra assurance.
- **Split update/render object dispatch (null-render pointer)** — distance-cull + bbox-cull already capture the culling win; a second pointer costs +2 bytes/SST against the open $50→$48 shrink goal for marginal call-overhead savings.

## 5. Already covered / myths busted

**We already do these (often better) — don't re-chase:**
- **DMA queue** (deferred VBlank burst + byte cap + 128KB split + priority bands) — dma_queue.asm has 3 priority sub-queues + compaction-persist, a superset of SGDK and S2's 18-slot. We also already fixed the half-written-Plane_Buffer race (b96c861). SGDK's temp-copy staging solves a hazard our stable RAM buffers don't have. ([SGDK](#))
- **Wrapping-torus nametable streaming** with `$80` autoincrement (plane_buffer.asm emits `$8F80`) and camera-speed cap (CAM_MAX_Y_STEP=16) — this *is* our locked continuous-scroll model; SGDK MAP is external confirmation. ([SGDK MAP](#))
- **Build-time flip-aware tile dedup** (tile_dedupe.py canonicalizes over identity/H/V/HV) — matches SGDK rescomp. ([SGDK rescomp](#))
- **Bucket-sort sprite priority** (8 bands via a single `lsr` of render_flags — no ID indirection, *better* than "store offset not ID"), **link-chain rotation** for graceful overload flicker (sprites.asm:200), **multi-part metasprite** branch (RF_MULTISPRITE sibling walk, budget-guarded, awaiting boss content), **exact-pixel cull** (beats the classic 6/7 size-byte cull). ([S3K/SGDK sprite mgmt](#))
- **DPLC sprite-art streaming, frame-change-gated** — our locked art path (§2.1); note the finding's `$3A`/`$780` addresses are S3K's, **ours are SST_mapping_frame + DPLC window at tile $3C0**.
- **S4LZ = the word-aligned streaming LZ** (LZ4W's slot), **already optimally-parsed** (s4lz.py forward DP, not greedy), with the **canonical 68000 inner-loop recipe** (jump-table length dispatch, literal batching, 14-deep unrolled `move.w`). Audit comes back negative on "is the packer greedy?" — it isn't. ([LZ4W](#), [bigmessowires](#))
- **Block-independent framing + per-block build-time dictionaries** (ojz_block_gen.py, 768B = staging-slot = collision granularity) — the KosM-precedent streaming-to-VRAM pattern, already tuned. ([KosM](#))
- **Block-embedded 16×16 collision** with shared height/width/angle maps + **dual-path solidity** — exactly our locked model (path-B *format* ships; path-B *content* is a byte-copy, deferred for loops).
- **objects-v2 SST** (uniform header, word code_addr, once-per-frame walk, O(1) free-slot stack, movem.l archetype burst) — the S3K SST lineage, improved. Stride is **$50** (not 74).
- **PC-relative jump-table dispatch, ADD Dn,Dn over shift-by-1, SWAP for free 16-bit shift / 16.16 integer-part read, tail-call jmp** (s4lint W020), **tst over cmp#0** — all locked conventions, all confirmed optimal.
- **stopZ80 around every RAM-source DMA** — structurally guaranteed (all DMA fires inside the VBlank stopZ80 bracket). **One caveat to carry forward:** if §9.7 cooperative S4LZ streaming ever fires DMA mid-frame, it must add its own bracket — Exodus will never catch the omission.
- **Per-scanline VSRAM column deform** (40-entry buffer, 16px floor), **HInt FIFO mid-line writes**, **Shadow/Highlight lighting**, **RAM-patched HBlank dispatcher** (hblank.asm:9-10), **multi-band shift-add parallax** (mul-free, ~410 cyc — *beats* TF4's 16-mul ~1120 cyc), **segregated ring/effect pools** — all designed/shipped in §4/§7.
- **Echo ESF flat event stream + shared BGM/SFX vocabulary, SMPS override-restore + numeric priority tiers, Mega PCM 2 ring + priority + request-table, dual-PCM read-ahead buffer** — all independently built (song format v0, `SCF_SFX_OVERRIDE`, our 256-byte ring + `SND_CTRL_DMA_ACTIVE` bracket).

**Myths / hazards busted:**
- **S3K "vector projection" landing** — confirmed a myth; we use classic motion-quadrant + angle-band (locked).
- **zgm "constant-time opcode dispatch" for music timing** — myth-adjacent over-generalization. Only helps when tempo == loop-repetition-rate (zgm's model). Our tempo is decoupled via a Timer-A overflow accumulator, so per-opcode jitter is **inaudible**; padding events to fixed width is pure ROM bloat. We already hand-balance the only loop that matters (the per-sample DAC).
- **"4-channel DAC @ 14 kHz is a free Phase-2 target"** — busted. Our single channel runs ~8.9 kHz at 400 cyc because the loop does dispatch + Timer-A poll + DMA-flag check, not a tight pure-mix inner loop. Honest ceiling is **2 channels with a rate drop**.
- **"Parallax cost = per-band math"** — busted. Our ~20%/47k-cycle cost is the **per-line HScroll buffer fill across 224 lines** (locked-mandatory for smooth banded vertical parallax), NOT the ~410-cyc mul-free band math. A frame-counter table doesn't reduce it.
- **SGDK "park off-screen sprites at off-screen Y"** — would *regress* us: parked sprites still burn one of 80 SAT slots; our drop-from-band-list frees the slot.

**Reject outright (hardware-unstable or locked-decision conflicts):**
- **VDP $C0001C debug-register plane-blending / PSG volume-boost** — unstable on ~30% of Model-1 units (315-5313 fab variance → metastable CRAM corruption), broken on some PAL revisions, can corrupt VRAM. Directly violates our hardware-stable stance; S/H covers 90% of the perceived benefit safely. If ever wanted for a one-off intro, flag explicitly as a do-not-run-on-real-hardware bet.
- **LUMINARY per-component-type ECS lists** — the 68000 has no data cache, so the locality argument is null; pointer-chasing adds `movea` cost vs our flat slot sweep. Conflicts with the locked code_addr dispatch.
- **MDSDRV VBlank-ack handshake / chip-write-log formats (XGM/zgm) / aPLib / UFTC16 / Echo wholesale** — each conflicts with a locked decision (flag-bracket DMA survival, sequenced MegaDAW format, two-tier byte/word-aligned compression). aPLib/UFTC are also *worse* ratio than ZX0/S4LZ, and our rule bars any new format that doesn't *beat measured* numbers.
- **Z80 LDIR→LDI unrolling for the DAC loop** — would destroy the equal-cost cycle-balance invariant that keeps the DAC clock rock-steady; anti-applicable.
- **Scc-mask branchless conditionals, sprite multiplexing, incremental insertion-sorted depth list** — no branch predictor to beat (fall-through is already cheap), no >80-sprite content, fixed priority bands suffice for a platformer; each trades clarity/budget for granularity we don't need.

## 6. Suggested next probes

1. **Prototype the 2-channel DAC mixer cycle balance (Phase 2 spike).** The whole win hinges on re-deriving FILL==SKIP==DRAIN for an additive+scale-LUT loop. Spike just the inner loop, count cycles by hand, render via vgm2wav, and report the achieved rate *before* committing to a channel count. This is the one genuine non-trivial win and the riskiest assumption.
2. **Wire Echo-style SFX channel-lock + BGM save/restore into Flamedriver Phase 5.** Snapshot the displaced channel's BGM state at lock, restore at unlock — and check whether this resolves the audited "SFX-steal clobbers SCF_KEYED / silence gap" (B1/A1) bugs directly. Combine with the PollPCM poll to also close the "one-shot DAC never stops" (C1) issue.
3. **Land the SAT-DMA-length change and measure the max-diagonal lag delta.** Trivial code; instrument `Lag_Frame_Count` over a long high-motion circuit with light vs heavy sprite load to confirm the reclaimed ~600 bytes/frame actually moves the ~76% lag number.
4. **Apply the two doc corrections (SMC prefetch, signed-`asr`) and grep-audit for latent exposure.** Beyond the doc fix, scan for any `asr` on a signed velocity/position that assumes round-toward-zero, and any planned SMC site (DPLC-base / plane-fill-base patch) to confirm the 2-word separation holds before it's written.
5. **Add the build-time 128KB-straddle assert as part of (not before) the windowed-art-streamer plan, and refresh `dma-queue-audit.md`.** Probe how the paged OJZ_ACT_POOL blobs currently land relative to $20000 so the assert has a known-good baseline when the streamer lands.