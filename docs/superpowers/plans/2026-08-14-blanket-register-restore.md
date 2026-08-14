# Blanket VDP register restore — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Delete `set_reg`'s paired `reset` parameter and the raster program's init words, replacing per-op frame-top restore with an unconditional VBlank re-blit of the VDP shadow — so two independently-authored presets can touch the same register without having to agree.

**Architecture:** `Flush_VDP_Shadow` currently writes only registers whose dirty bit is set. Making it unconditional means every mid-frame register write is undone at frame top for free, which is how Gunstar and Alien Soldier clobber registers with no per-effect cleanup. That removes the *reason* init words exist, which in turn removes the `init_count` coupling that the water patch offset depends on.

**Tech Stack:** `.emp` (sigil), `engine/system/vdp_init.emp`, `engine/effects/raster.emp`, `engine/effects/raster_dsl.emp`. **Byte-changing in both canonical shapes → full refreeze ritual and sigil pairing.**

**Line numbers verified against aeon master `561ea028` / sigil `94992706`.**

---

## Amendments (2026-08-14, at execution time — user-ruled)

Two rulings taken before Task 1, both expanding the plan as written:

**A. `VDP_Dirty_Mask` is DELETED, not kept.** The plan's Task 2 said to keep `clr.l VDP_Dirty_Mask`
"so `Set_VDP_Reg` callers do not accumulate stale bits" — circular reasoning. Once the flush is
unconditional the mask has **zero readers**; its only two were the `beq .done` early-out and the
`lsr.l`/`bcc` gate, both of which Task 2 deletes. Verified writer sites that become dead:
`parallax.emp:264,462` · `hblank.emp:62,67,83` · `boot.emp:301` · `demo_state.emp:54` ·
`object_test_state.emp:122,312` · `ojz_scroll_test.emp:96,266`, plus both `clr.l`s in `vdp_init.emp`.
Leaving it would be a dormant scaffold. This also **removes Task 1's flagged `bset` risk entirely** —
`Set_VDP_Reg` no longer touches a mask, so there is no byte-only-`bset`-on-memory hazard to verify.

Checked and NOT affected: raster effects never touch the mask (`set_reg` goes straight to `VDP_CTRL`,
`raster_dsl.emp:119`); the `$8F80` autoincrement excursions bypass the shadow entirely; parallax's
reg `$0B` write behaves identically under a blanket flush.

**B. Reg `$0F` gets a DEBUG-shape assert, not just a comment.** The plan's closing note already said
"if that ever needs to be real, the answer is an assert in the excursion sites" — do it now, in this
parcel. Use the `assert.*` idiom that self-gates to zero bytes in the plain shape
(`engine/sound/sound_api.emp:230`). The comment work in Task 2 Step 2 still happens; the assert is
in addition to it, not instead.

**Unverified claim carried into execution.** The header's "~200 cycles cheaper" has NOT been
measured. It rests on today's loop being O(highest dirty bit) — it pays the shift/branch/increment
per register *scanned*, even skipped ones. Plausible, but when the highest dirty bit is low
(parallax alone dirties reg `$0B`) blanket could be a wash. **Do not repeat the number as fact in
any commit message or doc until measured.** The parcel's justification is structural regardless.

---

## Why this, and what it is NOT for

The payoff is **structural, not performance**. It deletes ~24 bytes of ROM and ~56 cycles/frame — noise. What it actually buys:

- Two presets touching one register stop being a build error (`prog_init`'s disagreeing-resets `ensure`, added 2026-08-14 as a wrong-pixel fix, is the current composability ceiling).
- `WATER_TEMPLATE_ARM0_OFF`'s dependence on `init_count == 1` evaporates.
- `region_boundary`'s `sh: 1` stops being secretly load-bearing — today a lava line must write a no-op `set_reg($8C81, $8C81)` purely to manufacture an init word.

A pleasant surprise from the feasibility study: the blanket restore is **~200 cycles cheaper** than today's flush, because the current loop is O(highest dirty bit), not O(dirty count).

## The two risks, stated up front

**1. Reg `$0F` (autoincrement) is safe by CONVENTION, not construction.** Three main-loop sites do `$8F80` excursions (`engine/level/bg.emp`, `engine/level/section.emp`, `engine/level/plane_buffer.emp`) and are safe only because they mask IRQs to `$2700`; one VBlank-context site restores before yielding. Today's dirty gate makes a mid-excursion clobber *structurally impossible*. The blanket trades that for a comment. A future unmasked `$8F80` window would become a silent VRAM spray with no gate to catch it.

**2. You are deleting a mechanism and must REPLACE it.** Nothing in the tree writes shadow byte `$0C`. Both dense constructors expose `init_word` specifically so a section can want Shadow/Highlight globally ON. Ship `set_vdp_reg` in this parcel or that capability silently becomes a hardcoded boot constant.

---

## File structure

| File | Change |
|---|---|
| `engine/system/vdp_init.emp` | `Flush_VDP_Shadow` becomes unconditional; add `Set_VDP_Reg`; drop both `clr.l` |
| `engine/ram.emp` | delete `VDP_Dirty_Mask` (amendment A) |
| `engine/level/parallax.emp`, `engine/system/hblank.emp`, `engine/system/boot.emp` | drop dead `ori.l` dirty-bit writes |
| `games/demo/demo_state.emp`, `games/sonic4/test/object_test_state.emp`, `games/sonic4/test/ojz_scroll_test.emp` | drop dead `ori.l` dirty-bit writes |
| `engine/effects/raster_dsl.emp` | `set_reg` loses `reset`; delete `op_init`, `prog_init`; `sh_on` collapses; `raster_words`/`raster_program` lose the init header |
| `engine/effects/raster.emp` | delete the init loop; `WATER_TEMPLATE_ARM0_OFF` 6→4; `Raster_Program_None` shrinks; drop `rgp_init_*` and `rrp_init_*` |
| `games/sonic4/data/parallax/configs.emp` | both hand pins re-authored; the `init_count == 1` invariant block deleted |

---

## Task 1: `Set_VDP_Reg` — the shadow writer (do this FIRST)

Without it, Task 3 silently removes a capability.

**Files:** Modify `engine/system/vdp_init.emp`

- [ ] **Step 1: Read the existing flush to match its idiom**

```bash
sed -n '44,70p' engine/system/vdp_init.emp
grep -n "VDP_Shadow_Table\|VDP_Dirty_Mask" engine/ram.emp   # :147, :149
```

- [ ] **Step 2: Add the writer beside the flush**

Register index → shadow byte offset is the identity (`VdpShadow` is one byte per register, `$00`-`$12`, `engine/structs.emp:283-303`). Write the byte and set the dirty bit; the flush is what reaches hardware.

```emp
// Set_VDP_Reg — the ONE way to change a VDP register outside VBlank and have it
// survive to the next frame. Writes the shadow byte; the unconditional flush at
// frame top is what reaches the hardware.
//   d0.w = register index ($00..$12)   d1.b = value
pub proc Set_VDP_Reg (d0: u16, d1: u8) clobbers(a0) {
        lea     VDP_Shadow_Table, a0
        move.b  d1, (a0, d0.w)
        rts
}
```

**Per amendment A there is no dirty bit and so no `bset` hazard** — the original plan's warning about
byte-only `bset`-on-memory is void. Do not add a mask write "for symmetry"; Task 2 deletes the mask.

Note the `clobbers` set shrinks to `a0` (`d0` is no longer modified). Match whatever the surrounding
procs do for an index-into-table idiom.

- [ ] **Step 3: Build**

```bash
export SIGIL_BUILD=/home/volence/sonic_hacks/sigil/target/release/sigil
export SIGIL_EMIT=/home/volence/sonic_hacks/sigil/target/release/emit_sound_blob
DEBUG=1 ./build.sh 2>&1 | grep -E "built:|error"
```
Expected: builds. An unreferenced `pub proc` still emits, so the CRC moves — that is fine, this parcel moves bytes.

- [ ] **Step 4: Commit**

```bash
git add engine/system/vdp_init.emp
git commit -m "feat(vdp): Set_VDP_Reg — the shadow-writing path a blanket restore requires

Nothing in the tree wrote shadow byte \$0C, so removing the raster init words
without this would silently turn both dense constructors' init_word parameter
into a hardcoded boot constant. Pays part of the ledgered set_vdp_reg adoption
debt noted at engine/level/parallax.emp:262."
```

---

## Task 2: Make the flush unconditional

**Files:** Modify `engine/system/vdp_init.emp:44-70`

- [ ] **Step 1: Replace the gated walk with a straight 19-register blit**

Delete the `beq .done` early-out and the `lsr.l/bcc` per-bit gate. **Per amendment A, also delete
both `clr.l VDP_Dirty_Mask`** (here and in `VDP_Shadow_Init`), the `VDP_Dirty_Mask` field in
`engine/ram.emp:149`, and all 11 dead `ori.l #(1 << …), VDP_Dirty_Mask` writer sites listed in the
amendment. Grep for `VDP_Dirty_Mask` afterwards — the only surviving hits should be prose.

Watch the drift-lock `ensure` at the top of `vdp_init.emp` and the comment above it: its whole
argument is about the `.l` dirty mask holding 32 bits. With the mask gone that reasoning is void, but
the `VDP_Shadow_len` bound still matters for the `dbf` counter — **re-author the comment to the real
surviving constraint rather than deleting the ensure outright.**

- [ ] **Step 2: Write the comment that carries the `$0F` invariant**

This is the risk from the header and it must not live only in a plan. At the new loop, state: the restore now writes reg `$0F` every frame, so any routine that changes autoincrement mid-frame **must** mask IRQs for the duration; name the three sites (`bg.emp`, `section.emp`, `plane_buffer.emp`). Add a one-line pointer at each of those three sites naming the flush as a second consumer of their SR-mask invariant.

- [ ] **Step 2b: Add the DEBUG-shape `$0F` assert (amendment B)**

Make the invariant a real gate, not just prose. Use the `assert.*` idiom that self-gates to zero
bytes in the plain shape (see `engine/sound/sound_api.emp:230` and `engine/debug/compression_selftest.emp:65`).

**RESEARCH COMPLETE (2026-08-14).** Findings below are verified with file:line evidence and empirical
builds. Three of them invalidate the obvious implementation:

**The predicate is `hs, #$0600` (IPL >= 6), NOT `eq, #$0700`.** Contexts are not uniform:

| Site | Context | Mask | Established by |
|---|---|---|---|
| `section.emp:237`, `:406` | main loop only | IPL 7 | hand-spelled `move.w #$2700, sr` at `:215`, restored `:438` |
| `bg.emp:148` | main loop only | IPL 7 | hand-spelled at `:74-75`, restored `:168` |
| `plane_buffer.emp:467/481/503` | **VBlank only** | **IPL 6** (hardware, on IRQ6 accept) | nothing — `VInt_DrawLevel` declares `requires(vblank)` at `:442`; re-entrancy impossible because `Flush_VDP_Shadow` runs at `vblank.emp:158`, earlier in the same handler |
| `vblank.emp:326` | VBlank only (`VInt_Lag`) | IPL 6 | **not an excursion** — writes the default `$02`, i.e. the shadow's own value |

The main loop runs at **IPL 3** (`boot.emp:307` `move.w #$2300, sr`), so IPL >= 6 is exactly
discriminating: unmasked main loop (3) fails, masked main loop (7) passes, VBlank (6) passes.

**The snippet:**
```emp
        if DEBUG == 1 {
            move.w  sr, d0
            andi.w  #$0700, d0
            assert.w d0, hs, #$0600     // IPL >= 6: no VBlank can land mid-excursion
        }
```
The `assert` self-gates to zero bytes on its own (`sigil crates/sigil-frontend-emp/src/eval/asm.rs:911-918`);
the outer `if DEBUG == 1` is required for the two SR-extraction instructions, which do NOT self-gate.
`move.w sr, dN` is fine — not privileged on 68000, engine runs supervisor, and it does not trip
`[proc.sr-undeclared]` (that fires only when SR is the *destination*).

**BLOCKER: `assert` may NOT be placed inside a `with z80_stopped { }` body.** Its raise rail ends in
`jmp (MDDBG__ErrorHandler_PagesController).l`, modelled as `Edge::TailOut`, which fires
`[context.escape]` — a zero-firing-by-contract family, so the build hard-fails. There is no
`AssertDesugar` exemption in `context.rs`. **Hoist each assert to just BEFORE the `with`, still
inside the masked span.**

**TRAP — sonic4 alone does not prove this.** `section.emp:235` is
`with z80_stopped if SOUND_DRIVER_ENABLED == 0 {`. With sound ON (sonic4) the gate is false, no region
is planted, and `[context.escape]` does not fire. Reproduced: `sigil build --game sonic4 --debug`
**succeeds** while `--game demo --debug` (sound OFF) **fails**. **Build BOTH games.**

**Placement (do not deviate — `d0` free-ness was checked per site):**

| Site | Where | Reg |
|---|---|---|
| `section.emp` | immediately before the `with` at `:234` — one span covers both `:237` and `:406` | `d0` |
| `bg.emp` | immediately before the `with` at `:144` | `d0` |
| `plane_buffer.emp` | **proc head at `:452`**, before `lea VDP_DATA, a6`. NOT at `:481` — no register is free there (`d0`,`d1`,`a0`,`a5`,`a6` all live, and that is exactly the proc's `clobbers` contract) | `d0` |

Do NOT place an assert immediately after a proc's own `move.w #$2700, sr` — that measures the line
above it and is vacuous. The recommended placements are ~200 lines and a `jbsr` away from the mask,
so a future refactor that moves either one gets caught.

Measured cost: ~28-38 bytes and ~55-60 cycles per site in DEBUG; **exactly zero in release**, proven
by CRC equality (`8b3dc951` with and without).

**Context that softens the risk framing:** a mid-excursion VBlank is ALREADY fatal at these sites via
the VDP address latch, independent of this parcel (`bg.emp:69-73`). The blanket restore adds no new
failure class at any masked site. The assert's value is pinning a pre-existing invariant, not
covering a new hole.

**Rejected alternatives** (researched, with reasons — do not silently revisit):
- *DEBUG "excursion in progress" flag checked by the flush*: only fires if a VBlank actually lands in
  a ~few-hundred-cycle window out of ~120,000/frame, so it can report green through a whole campaign;
  and the flush runs BEFORE `VInt_DrawLevel` in the same handler, so it structurally cannot observe
  the `plane_buffer` site at all.
- *Routing `$0F` through `Set_VDP_Reg`*: buys nothing real (the address-latch hazard dominates) while
  adding cycles and a shadow that transiently lies.
- *Converting the three sites to `with ints_off`*: this is the genuine end-state — sigil would PROVE
  the mask at compile time with zero runtime bytes. But `engine/irq.emp:29-33` deliberately lists
  these as hand-spelled, so it is a design reversal, and it collides with the `with z80_stopped`
  nesting. **Out of scope for this parcel; record it as follow-up work.**

- [ ] **Step 3: Build and boot**

```bash
DEBUG=1 ./build.sh 2>&1 | grep -E "built:|error"
```
Then load in oracle, press start, screenshot. **Expected: OJZ renders normally.** A blanket restore that writes a wrong shadow value shows up instantly as a broken plane base, wrong scroll mode, or a blank screen.

- [ ] **Step 4: Verify the raster fixtures still render**

Sections 0/1/2 carry raster fixtures. Confirm each still looks right — the flush now re-asserts every register at frame top, so a raster program that relied on *not* being restored would break here.

- [ ] **Step 5: Commit**

---

## Task 3: `set_reg` loses `reset`; init words are deleted

**Files:** Modify `engine/effects/raster_dsl.emp`, `engine/effects/raster.emp`

- [ ] **Step 1: Collapse the constructors**

- `set_reg(word: int)` — `raster_dsl.emp:99`. Keep the `$8000..$97FF` range check and the **reg `$0A` ban** (that one is about the schedule, not restore, and must survive). Delete the same-register check and the `reset` range check.
- `sh_on()` — `raster_dsl.emp:136` — becomes `set_reg($8C89)`.
- Delete `op_init` (`raster_dsl.emp:504`) and `prog_init` (`raster_dsl.emp:553`) entirely.

- [ ] **Step 2: Shrink the wire format**

- `raster_words` (`raster_dsl.emp:710`): header constant `2 + 4 + 2` → `1 + 4 + 2`; drop `n = n + prog_init(fires).len`.
- `raster_program` (`raster_dsl.emp:724`): `out = [prog_mask(fires), init.len] ++ init` → `out = [prog_mask(fires)]`.
- `Raster_Program_None` (`raster.emp:767`): `[0, 0, RASTER_ARM_PARK, RASTER_OPS_END]` → `[0, RASTER_ARM_PARK, RASTER_OPS_END]`.
- Delete the init loop in `Raster_VBlank` (`raster.emp:515`, the `.init:` / `dbf` pair) and its count load.
- Drop `rgp_init_count`/`rgp_init_word` (`raster.emp:273`, `:326`) and `rrp_init_count`/`rrp_init_word` (`:351`, `:423`), plus both constructors' `init_word` parameters and their ensures. **Sections that wanted global S/H now call `Set_VDP_Reg` instead** — say so in the constructor comment.
- Update the wire-format doc block at the top of `raster.emp` (the `init_count` / `init[N]` rows).

- [ ] **Step 3: Move the water patch offset**

`WATER_TEMPLATE_ARM0_OFF` (`raster.emp:780`) 6 → **2**. Three unconditional write sites use it —
`raster.emp:854`, `:863`, `:866`. They need no change if the constant is correct, but **verify by
reading each**.

> **CORRECTION (execution, 2026-08-14): this plan originally said 6 → 4. That was WRONG.**
> The header goes from `[mask][init_count][init_word][arm0]` (arm0 at byte 6) to `[mask][arm0]`
> (arm0 at byte **2**) — two words removed is 4 bytes, so 6 - 4 = 2. Byte 4 is now `opc0`.
> Caught by dumping the emitted template out of the built ROM instead of trusting the number:
> `0004 8A75 0000 …`, where `$8A75` = `$8A00 | (120-3)` is the priming arm word at +2.
> Had the 4 shipped, the water patch's `subq.w #1` would have decremented a record's `op_count`
> and `dbf` would have walked ~35k words of ROM as opcodes inside a raw interrupt handler.
> **Lesson: verify a computed offset against emitted bytes, not against the prose that derived it.**

- [ ] **Step 4: Re-author both hand pins**

`OJZ_TEST_HAND` (`configs.emp:359`) and `OJZ_WATER_HAND` (`configs.emp:484`): delete the `init_count` and init-word entries; every later index shifts. `OJZ_VSRAM_HAND` (`configs.emp:635`) loses its `0, // init_count` line. These pins are the parcel's real safety net — the `first_mismatch` + length ensures are what prove the new encoder emits what you think.

- [ ] **Step 5: Delete the `init_count == 1` invariant block**

`configs.emp` around `:458-476` — the long "designated survivor" argument exists solely to protect the coupling this task removes. Delete it and say in the commit that its subject is gone, so a future reader does not think it was lost by accident.

- [ ] **Step 6: Build until green, then verify on oracle**

```bash
DEBUG=1 ./build.sh 2>&1 | grep -E "built:|error"
```
Then re-run the P1 and P2 raster gates: the frame-top mechanism changed underneath both, so their evidence must be re-established, not assumed.

- [ ] **Step 7: Negative-probe the surviving guard**

The reg-`$0A` ban must still fire. Temporarily author `fire(100, [set_reg($8A6D)])` and confirm the build fails naming reg `$0A`. Revert.

- [ ] **Step 8: Commit**

---

## Task 4: Ritual and gate

- [ ] **Step 1: Both shapes + the replay net**

```bash
./build.sh 2>&1 | grep "built:" ; DEBUG=1 ./build.sh 2>&1 | grep "built:"
```
This parcel changes RAM/ROM layout **and** frame-top register behaviour. The replay hash is address-free by contract (`engine/system/replay.emp:10-16`) so a layout shift alone is safe, but a *behaviour* change is not. Verify both fixtures (`games/sonic4/data/replays/ojz_fixture.bin`, `ojz_slide_fixture.bin`).

- [ ] **Step 2: Rebuild BOTH sigil binaries, then repin**

```bash
cd /home/volence/sonic_hacks/sigil
cargo build --release -p sigil-cli -p sigil-harness
AEON_DIR=/home/volence/sonic_hacks/aeon SIGIL_EMIT=$PWD/target/release/emit_sound_blob \
  SIGIL_BUILD=$PWD/target/release/sigil cargo run -q -p sigil-harness --bin repin
```
A stale binary produces a green run against the wrong compiler.

- [ ] **Step 3: Refreeze with prose evidence**

```bash
SIGIL_EMIT=$PWD/target/release/emit_sound_blob SIGIL_BUILD=$PWD/target/release/sigil \
AEON_DIR=/home/volence/sonic_hacks/aeon \
cargo run -q -p sigil-harness --bin refreeze -- \
  --freeze blanket-register-restore --ab docs/benchmarks/effects-p3/<evidence>.md \
  --note "<one line>"
```

- [ ] **Step 4: Expect the two ritual failures and fix them**

Both hit on every byte-moving parcel: `repin_pins::generated_pins_match_the_hand_typed_baseline` needs its ledger rows re-booked with an explanation of the delta, and any new cross-seam symbol needs a `repin.toml` row plus a seam equ in `crates/sigil-cli/tests/act_descriptor_port.rs`.

- [ ] **Step 5: Full suite, aggregate totals only**

```bash
AEON_DIR=/home/volence/sonic_hacks/aeon SIGIL_EMIT=$PWD/target/release/emit_sound_blob \
  SIGIL_BUILD=$PWD/target/release/sigil cargo test --workspace --no-fail-fast 2>&1 \
  | grep -E "^test result" \
  | awk -F'[.;] ' '{gsub(/[^0-9]/,"",$2); gsub(/[^0-9]/,"",$3); p+=$2; f+=$3} END {print "TOTAL passed:", p, " failed:", f}'
```
Expected `3711 / 0`. **Never tail a test run** — a tail once hid 16 failures here.

- [ ] **Step 6: Merge aeon and sigil AS A PAIR**, each commit naming the other's hash.

---

## Self-review

**Ordering is load-bearing.** Task 1 before Task 3, or the `init_word` capability is silently lost. Task 2 before Task 3, or programs lose their restores before anything replaces them — every intermediate build must boot.

**What this does NOT do.** It does not touch the patch generalisation (patchable fires, N moving boundaries) — that is the next parcel, and it gets simpler because `WATER_TEMPLATE_ARM0_OFF` stops depending on `init_count`. It does not add `Set_VDP_Reg` callers beyond the capability replacement.

**Known gap carried forward.** After this, reg `$0F` safety rests on a documented convention rather than a structural gate. If that ever needs to be real, the answer is an assert in the excursion sites, not a return to dirty gating.
