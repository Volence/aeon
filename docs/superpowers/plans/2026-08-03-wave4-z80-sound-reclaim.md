# Wave-4 Z80 Sound Reclaim — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute the 2026-07-16 review's wave-4 sound items — the sound bug-fix batch (item 23) and the Z80 size-reclaim campaign (item 24) — recovering resident Z80 code space and closing seven real sound defects. Target: DEBUG headroom 86 B → ~300 B.

**Architecture:** Two Sigil-side precursors make the campaign mechanical and build-proven, then the Aeon-side work lands bug-fixes-first (per the review's stated ordering) followed by one size batch per Z80 module. All five Z80 modules are `.emp` (no `.asm` twins — the seam-1 twin deletion removed them), so there is no lockstep constraint; but every module's base address cascades, which is what precursor Task 2 exists to defuse.

**Tech Stack:** sigil `.emp` (Spec-2) + the sigil Rust toolchain (`seam1.rs`, `sigil-frontend-emp`), build via `SIGIL_BUILD=... SIGIL_EMIT=... [DEBUG=1] ./build.sh`, oracle emulator (FOREGROUND ONLY — never from subagents), sigil-harness strict suite + refreeze.

---

## Rulings already made (Volence, 2026-08-03)

- **Scope = review items 23 + 24.** Item 25 (sequencer H1-H3) is OUT — separate follow-on parcel.
- **VMA pinning: take the Option A precursor** (derive Z80 module bases from a running cursor in sigil) before the reclaim.
- **All three extra defects fold in:** sequencer B1 (PSG glide underflow), FM bug 11 (patch load clobbers pan), PSG M5 (unguarded detune fold).

## Stale-review corrections (verified against master @ 7d3dd18 — do NOT re-plan these)

The review predates the `.emp` flip; **every line anchor in it is stale**. Re-derived anchors are in the per-task tables below. Substantive corrections:

- **Driver B2 (Snd_LoadSong repost race, +8 B): DROP IT.** The corruption half is already closed — H-1 moved the slot clear ahead of the last param read (`z80_sound_driver.emp:1057-1058`), the 68k spins on `MUSIC_SLOT==0` *before* writing (`sound_api.emp:203-215`), and all params post under one bus hold. What remains is 68k spin latency only, which driver M1 (`.seq_clr` → `LDIR`) buys for −1 B instead of +8.
- **SFX S4 (DrainQueue 3-way max): DROP IT.** Review scored −15..25 B; the actual unroll measures **+3 B**. `Sfx_QueueEntryPtr` cannot be deleted (three other callers). Cycle-only win, no bytes.
- **FM micro (delete the two `nop`s in `Fm_YmWrite`): REJECT.** 2 B for the only address→data spacing regression in the whole ledger (≈21 T → ≈17 T).
- **Sequencer M2 (cache `sc_flags` in a register): effectively dead** — real saving is −5..12 T, not −40..60. Reject.
- **The review's ledger is systematically low.** `.emp` `preserves(...)` contracts prove a pile of push/pop brackets dead that the review had to assume load-bearing. Item-level corrections: `Fm_WriteFreq` −23 (not −14), `Snd_StartSample` −13 via `ldir` (not −6), shared DAC-park stub −13 across 9 sites (not ~−6), SFX S6 −16 (not −8..12), SFX S3 −32 (not −16..24), SFX S1 −19 (not −25..30, the carry plumbing eats it).
- **H3 is no longer cadence-sensitive.** The pads are now `pad_to_cycles(...)`, and the existing `ensure(cycles(.drain, .drain_end))` / `ensure(cycles(.draining, .stop))` spans at `z80_sound_driver.emp:448-452` *contain* both pads. A wrong T-total is a compile error. The review's "re-derive the balance by hand + VGM $2A histogram" precondition is obsolete.
- **Already fixed by the port** (do not re-plan): driver B4 (per-iteration-`ei` comment), the driver half of B5, `Fm_NoteOff` de over-claim, PSG dead labels `.skip_base_latch`/`.skip_rearm`, sound_tables placement header, sequencer B4/B5, SFX `QueueEntryPtr` header, SFX Stage-C countdown comment, sound_constants LFO self-contradiction + request-slot +$04 gap + the "keep < $80" guidance.
- **For the FOLLOW-ON parcel (item 25), a correction that must not be inherited:** the review calls sequencer H1's per-channel tempo gate "provably redundant." **It is not.** `Seq_Op_Tempo` ($F3) broadcasts mid-frame from inside channel N's tick, so channels 0..N run that frame's gate with the old mod and N+1.. with the new — a permanent accumulator phase offset. Hoisting to a global accumulator is *more* S3K-exact but IS a chip-stream change on that frame. Dormant only because no shipped song contains a tempo event. Its advertised "−2 B/channel RAM" is also **not collectable** (`sc_tempo_mod`/`sc_tempo_accum` live in the SeqChannel↔SfxChannel shared prefix that the `sx_pad+58 == sc_detune` invariant depends on).

## Global constraints

- **No emulator MCP from subagents** — all oracle work is done by the controller, foreground.
- Build (from `/home/volence/sonic_hacks/aeon`):
  ```bash
  SIGIL_BUILD=/home/volence/sonic_hacks/sigil/target/release/sigil \
  SIGIL_EMIT=/home/volence/sonic_hacks/sigil/target/release/emit_sound_blob \
  DEBUG=1 ./build.sh
  ```
  `build.sh` REFUSES non-canonical sonic4 sound shapes. SFX/hotkey testing uses the off-canonical profile directly: `sigil build --native --config-a -o s4.debug.bin`.
- **Rebuild the sigil binaries after every sigil-side change** (`cargo build --release -p sigil-cli && cargo build --release -p sigil-harness --bin emit_sound_blob`). Stale-sigil-binary is a known gate trap.
- **Stale-artifact trap:** delete the target ROM before building, assert fresh mtime after. The auto-commit daemon may plain-rebuild mid-session — byte-verify ROM vs `.lst` before debugging.
- `git add` exact paths only. Commit per task. Branch: `parcel/wave4-z80-sound-reclaim` off master (created).
- **Headroom ledger is the running score.** After every task: rebuild both shapes, record `stat -c %s engine/sound/generated/z80_sound_blob{,_debug}.bin` against the ceiling `SND_STATE_BASE = $18F0 = 6384`.
- Z80 apply-rules (from the review, still binding): the DAC stream loop's 195-cycle balance is **correctness (pitch), not perf** — never touch `z80_sound_driver.emp:327-364`. All audible-behavior changes need rendered-audio A/B, never register streams.

## Baseline (measured 2026-08-03, master @ 7d3dd18)

| shape | blob | ceiling | headroom |
|---|---|---|---|
| plain | 6172 B | 6384 | 212 B |
| DEBUG | 6298 B | 6384 | **86 B** |

ROM `s4.bin` crc `3add2a69` / 413224 B — matches `golden/provenance.toml` tip exactly. Clean A/B origin.

---

## Phase 0 — Sigil precursors

### Task 1: Branch + baseline

**Files:** none (git only)

- [x] **Step 1:** `git checkout -b parcel/wave4-z80-sound-reclaim`
- [x] **Step 2:** Baseline build; blob sizes + ROM crc recorded above; confirmed against provenance tip.

### Task 2: Derived Z80 module bases (Option A) — the safety precursor

**Why first:** the `.emp` `vma:` headers are **dead** (parsed into `Section::vma_base`, then overwritten at `seam1.rs:405-408` from `file_specs()`). That table *literally places* each module, and `emit_sound_blob` builds the blob by **per-section concatenation** (`seam1.rs:440-447`) — so a stale downstream base means the gap is **silently dropped** and the module lands N bytes before the address its own code was linked against. Every cross-module `call` then misses. Over-correction collides loudly (`relax.rs:253-290`); **under-correction is silent**. The only structural check is the total-length constant, which this campaign forces us to edit — so it cannot catch us. Today the pins are exactly tight (zero slack, both shapes), so all ~250 reclaimed bytes cascade through five base pairs.

**Files:** `sigil/crates/sigil-harness/src/seam1.rs`, `sigil/crates/sigil-cli/tests/{seam1_native_link,boot_port,tranche23_spelling_probes}.rs`, the five `aeon/engine/sound/*.emp` section headers

- [ ] **Step 1:** Replace the base lookup in `native_blob_doctored` (`seam1.rs:400-411`) with a running cursor: `sec.vma_base = Some(cursor); sec.lma = blob_lma(debug) + cursor; cursor += emitted_span;`. Soundness: Z80 section sizes are base-independent (intra-section `jr` relaxation is relative; cross-module refs are 3-byte absolute `call nn`), so one pass converges — no fixpoint needed.
- [ ] **Step 2:** Resolve the `handler_symbols` coupling (`seam1.rs:379-395`): it currently reads the sequencer base from `seq.vma_plain` *specifically to avoid* lowering the driver (the `:366-373` comment says so — lowering pulls `DacSampleTable` through `seam2::sound_layout` and re-enters the chain). Fix: lower the driver for **size only** with a placeholder `DacSampleTable` (a Z80 16-bit immediate; instruction length is value-independent). This is the one piece of real engineering in the task.
- [ ] **Step 3:** Delete `vma_plain`/`vma_debug` from `FileSpec` (`seam1.rs:78-79`) and the ten values at `:92-121`.
- [ ] **Step 4:** Demote `BLOB_LEN_PLAIN`/`BLOB_LEN_DEBUG` (`seam1.rs:27,29`) from build input to a **tripwire assert** — keep them as "the reclaim moved the number I expected" checks, now safe because they no longer participate in placement. Update to the current values.
- [ ] **Step 5:** Un-hardcode / update the three test constants: `seam1_native_link.rs:141` (the `0x0565..0x0CD7` handler window — derive it or widen it), `boot_port.rs:101-102`, `tranche23_spelling_probes.rs:135,139`.
- [ ] **Step 6:** Delete the now-provably-dead `vma:` attributes from the five `.emp` section headers, or (if the frontend requires the attribute) leave them and add a comment naming seam1.rs as the authority. **Do not leave them stating stale numbers.**
- [ ] **Step 7:** Rebuild sigil; rebuild both Aeon shapes. **Acceptance: byte-identical blobs to the Task-1 baseline** (this task is a pure refactor of *how* addresses are computed, not what they are). `SIGIL_STRICT_GATE=1 AEON_DIR=... cargo test --workspace` green.
- [ ] **Step 8:** Commit (sigil + aeon, two commits, cross-referenced).

### Task 3: `pad_to_cycles` dense mode — the H3 enabler

**Why:** the DRAIN/DRAINING pads are 19 and 21 `nop`s emitted by `pad_to_cycles` (`z80_sound_driver.emp:387,439`). An unconditional `jr $+2` costs 12 T in 2 bytes vs 4 T in 1 byte, so a dense pad is 3× denser. The two `ensure(cycles(...))` spans already **contain** both pads, so correctness is build-proven — no manual recount, no VGM histogram.

**Files:** `sigil/crates/sigil-frontend-emp/src/{eval/builtins.rs,z80_cycles.rs}`

- [ ] **Step 1:** Add the missing cost arm for unconditional `jr e` in `z80_cycles.rs:122-133` — currently absent, so it falls through to `Cost::Unknown` and hard-bails with `[cycles.unknown-op]`. `("jr", [t]) if is_sym(t) => Cost::Fixed(12)`.
- [ ] **Step 2:** Extend `eval_pad_to_cycles` (`eval/builtins.rs:595-655`, currently emits `rem/4` nops unconditionally) with a dense mode: `rem/12` unconditional `jr <next>` + `(rem%12)/4` nops. `rem` is already validated as a multiple of 4, and 12 is a multiple of 4, so the existing validation carries over.
- [ ] **Step 3:** Decide the surface: a `pad_to_cycles(target, measured, dense: true)` opt-in, or make dense the default. **Prefer opt-in** — dense pads change instruction mix, and other (future) callers may want nop-only padding.
- [ ] **Step 4:** Rebuild sigil, rebuild Aeon. **Acceptance:** DRAIN pad 76 T → 6×`jr` + 1×`nop` = 13 B (was 19); DRAINING pad 84 T → 7×`jr` = 14 B (was 21). **−13 B total, zero edits to `z80_sound_driver.emp`.** The `:450`/`:452` ensures must still pass — if they don't, the dense emitter's T-math is wrong.
- [ ] **Step 5:** Note in the commit: `jr` changes the R-refresh cadence (7 M1 cycles vs 21). R is unused by this driver — irrelevant, but recorded.
- [ ] **Step 6:** Strict suite green. Commit.

---

## Phase 1 — The bug batch (review item 23 + the three approved extras)

Lands **before** the size work, per the review's ordering: refactoring around known-broken code means touching the same routines twice. Net cost ≈ **+20 B** against 86 B DEBUG headroom — fits.

| # | Bug | Anchor | Δ | Class |
|---|---|---|---|---|
| 4.1 | **driver B1** — SfxChannels/duck/SeqChannels are power-on garbage until the first `Snd_LoadSong`; `Sequencer_Frame` falls to `.run_sfx` even with `SND_SEQ_ACTIVE=0`, so `Sfx_Frame` walks 7 garbage channels every frame from the first tick (wild chip/bank writes possible) | `z80_sound_driver.emp:204` | **±0** | oracle-INVISIBLE (emulators zero RAM) |
| 4.2 | **SFX B1** — `Sfx_DuckRamp` re-asserts volume on a STOPPED song's channels (no `SND_SEQ_ACTIVE` gate, unlike `Sfx_Restore:1066`) → PSG drone until next song load | `sound_sfx.emp:334` (insert after `.store`) | **+5** | audible |
| 4.3 | **SFX B2** — queue arbitration compares RAW priority; a bit7 SFX would carry +128 queue weight, contradicting the 7-bit model | `sound_sfx.emp:562` | **+2** | latent |
| 4.4 | **PSG #1** — `Psg_ApplyMod`'s floor guard clamps only NEGATIVE sums, so an exact-zero divisor reaches the chip (contradicts its own comment; `Psg_EmitNoiseClock:427-431` does it right) | `sound_psg.emp:344-346` | **+4** | audible |
| 4.5 | **sequencer B1** *(extra)* — PSG down-glide 16-bit underflow evades the overshoot snap; glides through wrapped space up to ~65536/rate frames | `sound_sequencer.emp:381` (`jr c,.psg_snap` off the `sbc`) | **+2** | audible |
| 4.6 | **FM bug 11** *(extra)* — `Fm_PatchLoad` writes `$B4` from the patch, clobbering `sc_pan`; `Seq_HookSetPatch` never re-asserts pan and pan is write-on-change, so the shadow never re-emits | `sound_fm.emp:244-251`; consumer `sound_sequencer.emp:1750-1761` | **+2** | audible |
| 4.7 | **PSG M5** *(extra)* — `Psg_NoteOn`'s detune fold has no range guard; negative detune on a divisor-1 note wraps to `$FFxx` | `sound_psg.emp:247-258` | **+5** | latent |
| 4.8 | **sequencer B2** — a vol-env body whose byte 0 is `$80` (Loop) wedges the driver inside the Timer-A tick (cursor 0 → `$80` → infinite loop; DAC starves) | assert in `tools/gen_sound_tables.py:463` `_emit_vol_env_emp()` | **0 Z80 B** | build-time |
| 4.9 | **SFX B4** — alias fields (`sc_noise_mode`≡`sx_priority`, `sc_detune`≡`sx_pad`) protected only by comments | `ensure`s in `sound_constants.emp:574,649-650` + `$F2`/`$F6`-never-emitted assert in `tools/sfx_transcode.py` | **0** | build-time |

**Reachability notes (why 4.4/4.5 are live, not theoretical):** `PsgDivisorTableZ` ships its **top 13 entries as `$0001`** (`sound_tables_z80.emp:52-53`), so an accumulator of −1 reaches exact zero and a glide rate > 1 wraps. 4.4 is reachable from **music**, not just SFX (`sound_sequencer.emp:469`, ModUpdate).

### Task 4: Bug batch

**Files:** `engine/sound/{z80_sound_driver,sound_sfx,sound_psg,sound_sequencer,sound_fm,sound_constants}.emp`, `tools/{gen_sound_tables,sfx_transcode}.py`

- [ ] **Step 1:** 4.1 — replace `ld (SND_SFX_QUEUE_CNT), a` with `call Sfx_StopAll` (3 B either way). Verified safe: `Sfx_StopAll` (`sound_sfx.emp:1312-1337`) clears SfxChannel `SCF_ACTIVE`+`sx_priority` ×7, QUEUE_CNT, both duck bytes, and **returns `a`=0** (`xor a` at `:1331`) so `:205-213`'s stores run unchanged; `clobbers(af,bc,de,hl,ix)` ⊂ Init's set; `sp` is set at `:153`, pre-`ei` at `:245`. Add a comment noting it RMWs garbage `sc_flags` on SeqChannels (harmless while `SND_SEQ_ACTIVE=0`/`CHCOUNT=0`). Fix the header comment "over the idle program" → "instead of".
- [ ] **Step 2:** 4.2 through 4.7 — one commit each, each with the reachability argument in the message.
- [ ] **Step 3:** 4.8 + 4.9 — generator/transcoder asserts. Confirm they FAIL on a deliberately bad input before accepting them (a build-time assert that cannot fire is not a net).
- [ ] **Step 4:** Rebuild both shapes; record the headroom ledger (expect DEBUG ≈ 66 B). Strict suite green.

---

## Phase 2 — The reclaim, one batch per module

Ordered SFX-first because the table eviction (5.1) defuses a page-boundary landmine that would otherwise constrain everything downstream.

### Task 5: SFX size batch (≈ −112 B)

| # | Item | Anchor | Δ |
|---|---|---|---|
| 5.1 | **Evict `SfxEligTable`/`SfxRouteSlot`/`SfxSlotRoute` to the banked window.** Read ONLY by `Sfx_SelectVoice`, called ONLY from `Sfx_BeginSound:838` — *after* `SetBank(SFX_BLOB_BANK)` at `:708`. Nothing between re-banks (`sound_fm.emp`/`sound_psg.emp` contain zero `SetBank` calls). Precedent: `SfxBlobWinTab:1627-1633`, `SeqOpcodeTable` | `sound_sfx.emp:1348-1414` | **−29** |
| 5.2 | **S6** — dedupe the two identical 23 B channel-record stride blocks | `:818-830` + `:862-873` | **−16** |
| 5.3 | **S1** — merge the duplicated id→blob resolve preamble into `Sfx_ResolveBlob` (29 B shared; sites 5 B + 4 B). Carry-return flag contract must be exact; the `push af`/`pop af` id-save in `SfxDispatch` stays OUTSIDE the callee | `:534-557` + `:700-722` | **−19** |
| 5.4 | **S5** — slot wipe 16-bit counter → `djnz` (10 B vs 14; `LDIR` form is 13 B, worse). Add `ensure(SfxChannel_len <= 255)`. ~880 T saved per SFX start | `:877-886` | **−4** |
| 5.5 | **S2** — build-time `SfxSlotKind` collapses the slot→kind double chase. Express as comptime const arrays (`SFX_ELIG`, `SFX_SLOT_ROUTE`) emitting all four tables, with `SfxSlotKind` derived as `comptime for i in 0..SFX_VOICE_COUNT { SFX_ELIG[SFX_SLOT_ROUTE[i]] }` — **provably** consistent, so no drift guard needed. Live precedent: `engine/level/tile_cache.emp:121`, `parallax_dsl.emp:53-96`. Table lands banked (post-5.1) ⇒ 0 resident cost | `:1509-1523` + `:1557-1571` | **−20** |
| 5.6 | **S3** — page-fit assert → drop the carry-propagate triplet at 6 remaining sites (8 pre-S2) | `:1472,1483,1510,1517,1533,1558,1565,1612` | **−24** |

- [ ] **Step 1:** 5.1 first, always. **Do not attempt 5.6 with the tables where they are** — the block sits at `$11DB` plain / `$1259` debug, and the plain shape has only **8 bytes** of upstream-growth tolerance before it straddles `$1200` and the assert goes build-fatal. Phase 1 alone spends +7 of that. Post-eviction the tables can be page-aligned in the banked region and the assert is unconditionally satisfiable at zero resident cost.
- [ ] **Step 2:** 5.2 → 5.5 in order, commit each, rebuild + ledger each.
- [ ] **Step 3:** 5.6 last. If the page-align mechanism turns out not to be expressible (see risk note below), take the **zero-risk fallback**: replace `ld a,0 / adc a,h / ld h,a` (4 B) with `jr nc,.x / inc h` (3 B) — **−1 B/site, −8 B total, no assert, no address dependency.**
- [ ] **Step 4:** Upgrade the three RHS-only `ensure(11 == CHROUTE_COUNT)` guards (`:1367,1398,1415`) to real measured guards `ensure(span(SfxEligTable) == CHROUTE_COUNT)`. The stale comment at `:1361-1366` claiming `.emp` has no emitted-length introspection is **false today** — `span()` exists (`dac_sample_tab.emp:57`, `sound_tables_z80.emp:137-139`). Also `:1479-1480` `ld a,(hl); ld b,a` → `ld b,(hl)` (−1 B).

**Risk note (5.6):** `align N` is claimed by SIGIL Spec-2 §4.8 / D2.29 to be item-position with a link-time congruence assert, but **it is not used anywhere in the tree** and the SFX reviewer could not confirm the emp frontend implements it. Spike it before depending on it; the fallback above is unconditional.

### Task 6: Driver core size batch (≈ −63 B, +13 from Task 3 = −76)

| # | Item | Anchor | Δ |
|---|---|---|---|
| 6.1 | **H1** — factor the 7× "clear slot + bump ack" mailbox tail into a two-entry helper (`AckSlot` clears `(hl)`, falls into `AckBump`; 10 B). Sites become `ld hl,SLOT` + `call` (6 B). `hl` dead at all 7 (re-verified) | `:520-524,539-543,555-559,566-570,577-581,600-604` (11 B each) + `:1217-1219` (bump-only, 7 B) | **−24** |
| 6.2 | **Shared DAC-park stub** — 9 exact `ld a,SND_REG_DAC_DATA` / `ld (SND_Z80_YM_A0),a` sites → 5 B helper, sites 5 B → 3 B. `a` dead at all 9; none sit inside a `cycles()` span (`.stop` is the span *end* at `:452`, so its body is excluded) | `:280,394,423,714,767,901,928,943,1009` | **−13** |
| 6.3 | **H4** — `Snd_StartSample` descriptor walk → `ldir`. `SND_ROM_PTR`/`LEN` are contiguous, `ds_ptr(+3)`/`ds_length(+5)` are contiguous, both LE. Guard with `ensure(SND_ROM_LEN == SND_ROM_PTR+2)` + `ensure(DacSample_ds_length == DacSample_ds_ptr+2)` | `:719-739` (29 B) | **−13** |
| 6.4 | **H2** — `SndDrv_SetBank` rept-8 → `djnz`. `djnz` clobbers `b`, and the proc declares `preserves(bc,de,ix,iy)` (`:783`, mirrored at `sound_sfx.emp:84`) — **the `.emp` contract checker makes the caller audit build-enforced**: flipping to `clobbers(bc)` fails loud at every stale importer | `:790-805` | **−10** (or −8 with `push bc`/`pop bc`, zero-audit) |
| 6.5 | **M1** — `.seq_clr` byte loop → `LDIR`; halves the ~660 B wipe (~27.7k → ~13.9k cyc), which also shortens the 68k's `await_slot` spin (the reason driver B2 is droppable) | `:975-983` (14 B) | **−1** |
| 6.6 | **M3** — `.chan_init` push/pop bc. **Build-proven now**: the one call (`Snd_RouteClassFlags:1130`) declares `preserves(bc,de,hl,ix,iy)` (`:1231`); no manual body-write proof needed | `:1099`/`:1180` | **−2** |
| 6.7 | **Micros** — `jp z,.music_stop` → `jr z` (`:531`, −1); `Snd_DacLookup` ×9 via shifts (`:663-674`, −1), or −5 if `DacSampleTable` is page-aligned (it is already FIRST in its `vma: $8000` section, `dac_sample_tab.emp:62-63`) with `ensure((DacSampleTable & $FF) == 0)` + `ensure(DAC_SAMPLE_COUNT*DacSample_len <= 256)`. `DAC_SAMPLE_COUNT=10`, `(10-1)*9 = 81 ≤ 255` ✓. Keep the trailing `or a` (add sets carry) | `:531`, `:663-674` | **−2..−6** |

- [ ] **Step 1:** 6.1 → 6.7 in order, commit each, rebuild + ledger each.
- [ ] **Step 2:** `ldir` (6.3, 6.5) is **supported by the emp lowerer** (`sigil/.../lower/code.rs:2058`) but **unused corpus-wide** — these are its first two uses. Land them adjacently and byte-gate once.
- [ ] **Step 3:** 6.1 verification: PING echo + `ACK_COUNT` monotonic over a play/stop/sfx/fade/tempo sweep.
- [ ] **NEVER TOUCH** `:327-364` (the hot streaming loop). The three `ensure(cycles…)` at `:448-452` now enforce this, but the rule stands independently.

### Task 7: FM size batch (≈ −70 B)

| # | Item | Anchor | Δ |
|---|---|---|---|
| 7.1 | **fm 1** — `Fm_WriteFreq` scratch round-trip (body 44 → 21 B, ~−111 T/call). Includes two dead `push de`/`pop de` brackets (`:995`/`:1001`, `:1009`/`:1011`) that the review missed — both provably dead via `preserves(de,hl)` on `Fm_RoutePart`/`Fm_YmWrite`. `Fm_Scratch*` grep-confirmed read/written ONLY inside `sound_fm.emp` | `:994-1021` | **−23** |
| 7.2 | **fm 1b** *(new)* — redundant `push de`/`pop de` around `call Fm_WriteFreq` | `:895-897` | **−2** |
| 7.3 | **fm M** — fold-clamp block repeated 3× (15 B each) → helper (16 B + 3 `call`) | `:434-443,454-463,484-493` | **−20** |
| 7.4 | **fm 3** — factor the 4× RoutePart+stash prologue (−12 after 7.1 removes WriteFreq from the set); plus PatchLoad's dead `push hl`/`pop hl` at `:227`/`:233` | `:227-233,496-500,631-635` | **−14** |
| 7.5 | **fm M** — PatchLoad header-write scratch reloads (hold ch in `e`; `Fm_YmWrite` preserves de) | `:236-251` | **−11** |
| 7.6 | **fm 2** — `Fm_SetVolume` calls `Snd_ChanClass` twice for mutually exclusive folds; one call dispatches both (−63 T, fires per note AND per duck/fade frame). Needs the global-atten fold reordered ahead of the env fold. Review's −5 assumed no replacement `jr`; one is needed | `:429` + `:473` | **−3** |
| 7.7 | **fm M** — `PatchOpGroup` re-reads invariants per op; hoist `ch` into `d` (`part` cannot be hoisted — no free register, `hl` is the patch pointer). ~−1050 T/patch load | `:286-308` | **−2** |

- [ ] **Step 1:** 7.1 first (biggest, and it removes `Fm_WriteFreq` from 7.4's set — take them in this order or the accounting double-counts).
- [ ] **Step 2:** 7.6 is **identical only under an argument**, not by construction: reordering the class-exclusive fold is output-preserving because every fold is a saturating add of a non-negative operand with a common ceiling (`$7F` for FM TL). **Verify by offline enumeration** (3 operands over an 8-bit domain), not by ear. Same for PSG in 8.2.
- [ ] **Step 3:** YM spacing check for 7.1 — data→next-address narrows ~93 T → ~63 T, still comfortably over the ~39 T floor. No other endorsed change touches spacing.

### Task 8: PSG size batch (≈ −23 B)

| # | Item | Anchor | Δ |
|---|---|---|---|
| 8.1 | **psg 2** — `PsgVolEnv_Resolve` / `FmVolEnv_Resolve` are byte-identical except three constants; merge via an explicit shared tail (`falls_into` for one head, `jr` for the other — the existing `falls_into` contract keyword expresses this and the checker verifies it). Review's −17 assumed both heads fall through; only one can | `sound_psg.emp:166-187` + `:199-220` | **−15** |
| 8.2 | **psg 3** — single `Snd_ChanClass` in `Psg_SetVolume` (+ deletes a push/pop), ~−84 T, hot via `PsgEnvUpdate`. −7 if the `preserves(hl)` contract is dropped (no caller needs hl — `sound_sequencer.emp:449,640,1744,1011`, `sound_sfx.emp:360` all have hl dead) | `:451-454` + `:493-496` | **−5..−7** |
| 8.3 | **psg M4** — `Psg_VolToAtten` rewrite (`cpl/and $7F/srl×3`, 9 B vs 12), frees `b`. **Proven** identical for all 256 inputs: new = `(($FF−v) mod $80)>>3`, old = `(($7F−v) mod $80)>>3`, and `($FF−v) ≡ ($7F−v) (mod $80)` | `:127-136` | **−3** |

- [ ] **Step 1:** 8.1 → 8.3, commit each, rebuild + ledger each.
- [ ] **Step 2:** Generics do NOT help 8.1 — instantiating per constant-set emits two copies, which is what we are deleting. Explicit shared tail only.

---

## Phase 3 — Comptime hardening (0 bytes, permanent nets)

### Task 9: Turn hand-audits into build-time invariants

- [ ] **Step 1: YM write-spacing ensures.** The review audited every YM write path by hand and marked it PASS. Make it structural: cut labels around each port write + `ensure(cycles(.addr_write, .data_write) >= 8)` and `ensure(cycles(.data_write, .next_addr) >= 39)`. **Caveat:** `[cycles.ambiguous-branch]` fires on the `jr nz,.partII` inside `Fm_YmWrite`, so the two straight-line halves must be measured separately. This is the single highest-value comptime addition in the parcel — it retires the spacing audit permanently and makes 7.1 safe by construction.
- [ ] **Step 2: table size asserts** (`sound_tables_z80.emp:27,41,55,73`) — `span(FmPitchTableZ) == (FMPITCH_MAX_IDX+1)*2`, `span(PsgDivisorTableZ)==190`, `span(LogVolumeLutZ)==256`, `span(CarrierMaskTableZ)==8`. Generator-emitted. `FMPITCH_MAX_IDX` currently trusts a comment.
- [ ] **Step 3: PSG env-byte ceiling assert** — every PSG env body byte `< $80` must be `<= $10`. A `$11` byte makes `$11+$0F = $20` pass `bit 4,a` and OR into the latch's channel-select bits (`sound_psg.emp:475-483`; env bodies max `$10` today at `sound_tables_z80.emp:86,107`).
- [ ] **Step 4: doc/comment truth pass** — `sound_fm.emp:10,41` + `sound_psg.emp:8-9` stale "INLINE, not banked" headers (the `sound_tables_z80.emp:8-9` twin is already correct); `tools/gen_sound_tables.py:265,283,285` legacy `.asm` emitter still prints the wrong claim; `dac_sample_tab.emp:20` "main.asm's phase block" → `soundBankHead`; `z80_sound_driver.emp:554` stale SfxDispatch comment; `:948-950` LoadSong "DAC loop is PAUSED" (false — the Timer-A tick services the mailbox, as `:986-990` itself says); `sound_sfx.emp:164` drain-tie "FIFO"; sound_constants `:43` SND_REQ_SFX "reserved (Phase 1C)", `:488` sfh_priority bit7 "RESERVED (Stage B)", `:486,491,493` sfh_gain/sfh_cap "INERT in Stage A", `:76` dead `SND_SAMPLE_TEST`; sequencer `:14,885,1658` stale `.asm` filename refs.
- [ ] **Step 5: document the two accepted edge cases** — FM `FnumApplyDelta` block-bit bleed at extremes (`sound_fm.emp:784-814`, unreachable at ±127 detune) and its sequencer twin (`sound_sequencer.emp:808-846`, `FNUM_HI=$0508` so only block 7 with fnum ≥ $800 reaches it). Comment, do not spend bytes.
- [ ] **Step 6: sequencer B6 contract comment** — `Sequencer_StopAll` (`:1783-1805`) touches only `SND_SEQ_ACTIVE`, never per-channel `sc_flags`, so `SCF_KEYED`/`SCF_ACTIVE` go stale. Known and worked around at both consumers; record it as a contract.

---

## Phase 4 — Verification and freeze

### Task 10: Oracle A/B + rendered audio

Per `sigil/crates/sigil-harness/golden/ab/AB_PROTOCOL.md`. Sound needs a **sound-specific state-identity bar** — the standard framebuffer/VRAM bar is blind to this parcel.

- [ ] **Step 1: the PS-sound bar.** Deterministic drive from `emulator_reset`, frame-anchored (never press-count), OLD vs NEW at ≥3 anchors spanning music playback + at least one SFX. At each anchor assert byte-identity of: the Z80 **state block** `$18F0-$18FC`, the **mailbox/status** `$1F00-$1F14`, the **DAC ring contents**, and FM/PSG chip state (`emulator_get_channel_states`). **Documented tolerance:** `SND_RING_RD`/`SND_RING_WR` may differ — the ring lead is self-correcting and 6.1/6.5 shift Timer-A tick cost slightly. Assert the lead stays within its proven bound (PRIME 128 ≤ TARGET 200 < 256) rather than demanding equality. The code region `$0000-$18F0` obviously differs — that is the parcel.
- [ ] **Step 2: rendered-audio A/B for the audible fixes only** — 4.2 (StopMusic mid-PSG-note → ducking SFX → confirm no post-SFX drone + oracle-read PSG latches), 4.4 + 4.5 (high-note fast-down-glide probe; top 13 divisors are 1), 4.6 (song with mid-song `MEV_PATCH` after `MEV_PAN`). VGM → wav, energy + spectrum. **VGM capture is realtime-only** — do not attempt it in deterministic mode.
- [ ] **Step 3: `mt_ref.vgm` onset diff** for the no-change case — the whole reclaim must be chip-stream identical on Moving Trucks. Use `tools/vgm_onsets.py`. Any onset delta is a bug, not a tolerance.
- [ ] **Step 4: SFX smoke** — off-canonical profile (`sigil build --native --config-a`), one SFX per kind, by-ear pass. 4.1 is oracle-INVISIBLE (emulators zero RAM at power-on) — verify it by *reasoning* + a deliberate garbage-poke into the SfxChannel region before the first `Snd_LoadSong`, confirming `Sfx_StopAll` cleans it.
- [ ] **Step 5:** Write the evidence note to `docs/superpowers/notes/2026-08-03-wave4-sound-ab.md`. It must be durable — `refreeze --ab` records it as the proof the anchor move was earned.

### Task 11: Refreeze + docs

- [ ] **Step 1:** `refreeze --freeze wave4-z80-sound-reclaim --ab docs/superpowers/notes/2026-08-03-wave4-sound-ab.md`; `refreeze --check` green; `repin --check`; `SIGIL_STRICT_GATE=1 cargo test --workspace`; clippy.
- [ ] **Step 2:** PROVENANCE.md narrative entry (sigil), following the established chain format.
- [ ] **Step 3:** Update `docs/reviews/2026-07-16-emp-port-optimization-review.md` — mark items 23/24 executed, record the dropped items (driver B2, SFX S4, the FM nop micro, sequencer M2) with their reasons, and carry the sequencer-H1 correction forward so item 25 does not inherit the bad premise.
- [ ] **Step 4:** `docs/BUGS.md` entries for the seven fixed defects.
- [ ] **Step 5:** Final headroom ledger in the merge commit. Update `docs/DEFERRED_WORK.md` with the item-25 follow-on (≈ −71..−94 B still available in the sequencer) and the deferred edge cases.
- [ ] **Step 6:** Merge to master.

---

## Projected ledger

| phase | Δ plain/DEBUG |
|---|---|
| Phase 1 (bug batch, 7 fixes) | **+20** |
| Task 3 (H3 dense pads, sigil-side) | −13 |
| Task 5 (SFX) | −112 |
| Task 6 (driver core) | −63 |
| Task 7 (FM) | −70 |
| Task 8 (PSG) | −23 |
| **Net** | **≈ −261** |

DEBUG headroom **86 B → ≈ 347 B**. The review hoped to "roughly triple" it. Plain headroom 212 B → ≈ 473 B.

Every byte figure above is a static instruction-encoding count, not a measurement. The build's own blob-size readout is the arbiter after each task.
