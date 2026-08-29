# The column-19 borrow: fixing the leftmost partial column, and what it costs

**2026-08-29, branch `parcel/fg-left-edge-vsram`. This lane has no emulator.** Every claim is
either read from source (ours, Oracle's, Genesis Plus GX's, a reference disassembly's), quoted
from a primary online source, or derived — and each is labelled which. Nothing here was
measured on a running machine by this lane; the runtime confirmations it wants are listed at
the end as TAGs for the controller.

Subject: `d-40`, ruled by the owner for the real fix — *"ok how is coveringg it or leaving it
acceptable?"*, *"Is there nothing to actually fix it?"*, *"let's tryy the fix"*. The two
predecessors are `docs/research/2026-08-27-fg-left-edge-reproduction.md` (the measured
reproduction) and `docs/research/2026-08-28-deform-scene-left-edge-triage.md` (the triage).

---

## 1. The mechanism, re-derived from source

### What our engine writes

`Parallax_Step5_Vscroll` Step 5b (`engine/level/parallax.emp`) fills the 20-entry column
buffer. Per column-pair it writes **FG word first, then BG word**:

```
        move.w  d1, (a2)+                           // FG word = camY (constant per column)
        move.w  d2, d0
        add.w   d5, d0
        move.w  d0, (a2)+                           // BG word = base + offset
```

`d1` is `camY`, loaded once before the loop and never touched inside it, so **all twenty FG
words are the same value**. `Vscroll_Write` then ships all twenty longwords to VSRAM $00
onward with autoincrement 2. So VSRAM $4C (column-pair 19, plane A) has always carried the
foreground's V-scroll, and $4E has carried plane B's own scroll plus the wobble sample.
**READ FROM SOURCE.**

### What the VDP does with column-pair 19

Genesis Plus GX, `core/vdp_render.c`, `render_bg_m5_vs` (downloaded from `ekeeke/Genesis-Plus-GX`
master this session; the same block appears five more times in the file, once per per-column
renderer variant):

```c
/* Left-most column vertical scrolling when partially shown horizontally (verified on PAL MD2)  */
/* TODO: check on Genesis 3 models since it apparently behaves differently  */
/* In H32 mode, vertical scrolling is disabled, in H40 mode, same value is used for both planes */
/* See Formula One / Kawasaki Superbike Challenge (H32) & Gynoug / Cutie Suzuki no Ringside Angel (H40) */
if (reg[12] & 1)
{
  yscroll = vs[19] & (vs[19] >> 16);
}
```

`vs` is `(uint32*)&vsram[0]`, so `vs[19]` is column-pair 19's longword and `x & (x >> 16)` ANDs
its two halves: **`VSRAM[$4C] & VSRAM[$4E]`**. `yscroll` is initialised to 0 and stays 0 outside
H40. The same `yscroll` is then used by the plane-B block *and* the plane-A block, each gated on
**its own** `shift = plane's hscroll & 0x0F`.

**This is the load-bearing structural detail, and it is the one the brief did not have.** In the
same function:

```c
  if(shift) { ... dst = (uint32 *)&linebuf[0][0x10 + shift]; ... DRAW_COLUMN(atbuf, v_line) }
  else      { dst = (uint32 *)&linebuf[0][0x20]; }

  for(column = 0; column < end; column++, index++) { ... vs[column] ... DRAW_COLUMN(...) }
```

The visible screen starts at linebuf offset `0x20` and `end` is 20 in H40. So a plane with
`shift != 0` lays out as:

| screen x | VSRAM entry used |
|---|---|
| `0 .. shift-1` | the AND value (`VSRAM[$4C] & VSRAM[$4E]`) |
| `shift .. shift+15` | pair 0 |
| … | … |
| `shift+288 .. shift+303` | pair 18 |
| `shift+304 .. 319` | **pair 19** |

**Column-pair 19 is not only the latch the leftmost column borrows from — it is also the entry
that renders the RIGHT edge.** With `shift == 0` it renders the full rightmost 16 px. That is
the fact that sets this parcel's price, and §4 is about it.

### Oracle agrees on the value and diverges on the extent

`/home/volence/sonic_hacks/oracle/crates/oracle-core/src/render.rs`, `fn plane_vscroll` (read at
oracle `6447ea1`, the current tip of its `main`; the brief cited `e23001a`, which is a real but
older commit on the same branch — the function is unchanged between them):

```rust
} else if hscroll & 0x0F != 0 && x < 16 {
    // R8 partial left column: shared value both planes.
    if h40 {
        self.vsram_word(38) & self.vsram_word(39) // VSRAM $4C (col-19 A) & $4E (col-19 B)
```

Same AND, same both-planes, same H40 gate. It differs in two ways, both of which Oracle's own
comment and its divergence ledger already flag as interim: the extent is the whole leftmost
16-px column rather than `hscroll & 15` px, and `plane_vscroll` takes one `hscroll` rather than
each plane's own. **For validating this fix that divergence is conservative, not dangerous** —
for plane A, post-fix, both models render the same value at every x (pixels `shift..15` take
pair 0 = camY under GPGX and the AND = camY under Oracle), and for plane B Oracle over-reports
the left-edge damage. Oracle cannot produce a false green here; it can only overstate the cost.

---

## 2. The sources, reconciled — and the tiers matter more than the count

| # | Source | Claim | Status |
|---|---|---|---|
| 1 | **Eke-Eke, SpritesMind t737 p3, 19 Aug 2010** | leftmost partial column = `VSRAM[$4C] & VSRAM[$4E]`, same value both planes, H40 only; in H32 it is fixed at 0 and "writing vscroll value to other VSRAM addresses had no effects"; hscroll mode is irrelevant | **HARDWARE-TESTED** — dedicated test program, PAL Model 2 (315-5660 ASIC). He later noted, unprompted, that he never tested a discrete-VDP Model 1 (315-5313). |
| 2 | **Genesis Plus GX source** | the code above | implementation of #1 |
| 3 | **Eke-Eke, t737 p2, 30 Jul 2010** | the "backward parse": plane A takes `$4E`, plane B takes `$4C` | **INFERRED, AND WITHDRAWN BY ITS OWN AUTHOR.** Three weeks later he wrote the test ROM and got #1 instead. |
| 4 | **fox68k, t737 p2** | implemented #3, "it does work for Cuty, Gynoug and F1" | eyeball on games, not a hardware test |
| 5 | **Plutiedev, hardware-issues** | column −1's vscroll is "garbage in earlier hardware and a copy of column 0 in later hardware"; VSRAM grew to 64 words "in model 2 VA4 onwards" | **ASSERTED**, no test cited |
| 6 | **Stef (SGDK), SpritesMind t1341, 2012** | "only fixed in genesis 3 VA3 as far i remember … only a few bits from the real value is taken in account" | **ASSERTED FROM MEMORY**, three hedges in two sentences |
| 7 | **Nemesis, t1291, 2013** | VSRAM read data is held in one internal latch register continuously updated by the render process; reads past the end return that latch's live state | **HARDWARE-TESTED**, on VSRAM read behaviour. Explains the shape of #1 (one latch → one value for both planes) without explaining the AND. |
| 8 | **Kabuto's hardware notes** | the VDP renders 2 extra tiles before the left border; "16 to 1 pixels of further plane data in the left border and 0 to 15 pixels thereof in the right border (both always sum up to 16)" | **HARDWARE-TESTED**, on fetch geometry |

**Correction to the brief, item 1.** The brief presents the AND rule and "the backward-parse
reading (Eke/fox68k)" as two live descriptions. They are not contemporaries: #3 is #1's own
**superseded hypothesis**, retracted by the same person on the strength of his own test. There
is exactly **one** controlled hardware test on this behaviour in the entire public record, it is
sixteen years old, and nobody has re-run it on a Model 1, a VA4 Model 2, or a Genesis 3.

**Correction to the brief, item 2 — the extent.** Three independent sources (GPGX's linebuf
arithmetic, Plutiedev's "the up to 15px to the left", Kabuto's "16 to 1 pixels") say the affected
region is `hscroll & 15` pixels, **not** a full 16-px column. The 16 in our tree is Oracle's
interim model, ledgered as divergence P4 in oracle's `docs/2026-07-16-vdp-pixel-known-differences.md`.
`d-40`'s own detail line already had this right (`w = (-camX) mod 16`); the reproduction doc's
"exactly two columns" reading is an artifact of measuring with the emulator whose model says 16.
This changes nothing about the fix — a narrower true extent only means fewer pixels were wrong
before it.

**Searched and found nothing** (so the absence is auditable rather than assumed): any post-2013
re-test of the rule; any hardware-tested statement about late-revision behaviour; Charles
MacDonald's `genvdp.txt` (404 at the usual mirror — and MacDonald is *in* both threads without
stating a rule, writing that he "may have not tested 32-cell mode and assumed the same rules
apply"); segaretro's VDP pages; the official Sega manual. The Mega Drive wiki
(`wiki.megadrive.org` / `md.railgun.works`) was **unreachable** — 502 and 404 on every attempt —
so its text is known to this lane only through a search-engine snippet and is not cited above.

---

## 3. What the reference disassemblies actually do — including one claim of ours that is false

Ten trees swept (S.C.E., Batman & Robin, Vectorman, Gunstar Heroes, Alien Soldier, Thunder Force
IV, Ristar, S3K, Sonic 2, sonic_hack), by `$8B0x` register writes, VSRAM write/DMA commands,
each game's VSRAM shadow buffer symbol, and keyword sweeps for two-cell / per-column / leftmost /
partial column. All findings **READ FROM SOURCE**.

| Game | per-column V-scroll | VSRAM pairs written | what it does about the left column |
|---|---|---|---|
| S.C.E. | yes (`$8B07`) | 20 | camera-X **round-up** before band select |
| Batman & Robin | yes (`$8B07`) | **20** | nothing found |
| Vectorman | yes (`$8B0C`/`$8B0F`) | 20 | nothing found |
| Gunstar Heroes | engine supports it; **bit 2 never set** | – | n/a |
| Alien Soldier | yes (`$f7e7` = 4/6) | 20 | nothing found |
| Thunder Force IV | setter exists, **no caller** | 1 pair | n/a |
| Ristar | yes (`$8B07`) | **21** in one H-int effect, 20 in the VBlank DMA | nothing |
| Sonic 3 & K | yes (`$8B07`, one site) | 20 | camera-X **round-up** before band select |
| Sonic 2 | no | 1 pair | n/a |
| sonic_hack | no (`$8B07` commented out) | 1 pair | n/a |

**`d-40`'s detail line says "Ristar and Batman & Robin gesture at it by writing 21 column pairs
into 20". That is wrong on both halves and it should not be carried forward.**

- **Batman & Robin writes 20, everywhere.** Its fill loops are `move.w #$13,d7` + `dbra` (= 20).
  The `move.w #$14,d7` values that look like a 21-count are exact element counts for a
  jump-into-unrolled-table copier (`lsl.w #$3,d7 / neg / jmp $b932(pc,d7.w)`), not `dbra` counts —
  the same routine is called with `#$e0` = 224 for the H-scroll table.
- **Ristar's 21 is real and is an off-by-one, not a trick.** At ROM `$00BE4A`, an H-int transition
  effect: `move.w #$14,d1` + `dbra` = 21 iterations of a two-word write starting at VSRAM `$0000`
  with autoincrement 2. Pairs 0–19 fill `$00`–`$4E`; the 21st lands at `$50/$52`, **past the
  40-word VSRAM**. It cannot reach slot 19 under any reading. Its source array (`$FFF500`) is a
  20-entry buffer in both of its layouts, so it reads one word past that too.

So: **no shipped game in this corpus uses the borrow.** The only mitigation anyone ships is
S3K's (inherited by S.C.E.) round-up of camera X to the next column when `camX & 15 != 0`, and
that addresses the *index shift* of the twenty good columns — slot 0 serving the first **full**
column — not the rendering of the partial one. It does not apply to us: in our per-column scenes
plane B's HScroll is identically zero, so plane B has no shift and no index skew, and the FG
words are constant so a skew could not show on plane A either. Recorded so the next reader does
not re-derive it.

Everything else documented is variant (a): cover the strip with sprites. rasterscroll.com:
*"the first column will show garbage tiles, so developers typically hid it using sprites"* —
Battle Mania 2. Gynoug simply shipped it. **The borrow appears to be undocumented publicly**;
that is a genuine absence from a targeted search, and it also means there is no external report
of someone trying it and hitting a snag.

Two incidental findings worth having on file:

- `sonic_hack/ENGINE_OPTIMIZATION_PLAN.md:1737` carries a stale claim about this bug —
  *"Workaround: mask leftmost column with a sprite, or ensure VSRAM entry 0 is zero."* The second
  half is wrong for H40: entry 0 is not what the partial column reads. (Legacy tree, not ours;
  noted, not edited.)
- **Oracle and GPGX disagree about VSRAM writes past `$4E`**: `oracle/crates/oracle-core/src/vdp.rs`
  masks `% VSRAM_SIZE` (wraps onto column 0), GPGX bounds-checks (discards). Irrelevant to us —
  we write exactly 20 pairs — but it would matter to anyone who tried Ristar's 21.

---

## 4. The fix, and the price — which is bigger than `d-40` priced it

### The fix

One instruction at the end of Step 5b's fill loop, inside the `CAP_PER_COL_VSRAM` producer span:

```
        move.w  d1, Parallax_Vscroll_Column_Buf + VSCROLL_COL19_BG_OFF
```

`d1` is still camY. Verified at the byte level in `s4.debug.bin`: `31C1 8942` =
`move.w d1,($8942).w`, and `$8942 − $88F4` (`Parallax_Vscroll_Column_Buf`) = `$4E` = 78 =
column-pair 19's plane-B word. 4 bytes.

**Producer, not emitter, deliberately.** The emitter is a 20-long straight-line burst inside the
VBlank VDP window; a special case there costs that window every frame and breaks a uniform run
for nothing. The producer owns the buffer's *contents*, runs outside the window, and the buffer
is the declaration of what VSRAM should hold — so a probe, a gate, or any future consumer reading
the buffer sees the truth rather than a value the emitter will later amend.

### It cannot make the leftmost column worse, under any rule on record

| rule | left column before | left column after | verdict |
|---|---|---|---|
| AND (hardware-tested) | `camY & bgV` | `camY & camY = camY` | **fixed**, and never worse: `camY & bgV` is a bitwise *subset* of `camY`, so it can only equal camY or differ from it |
| backward parse (withdrawn) | A takes `$4E` = `bgV` | A takes `$4E` = `camY` | **fixed exactly** — the write lands in the very entry that reading names |
| copy of column 0 (late hw, asserted) | already camY | still camY | inert, no harm |
| H32 fixed-zero (hardware-tested) | 0 | 0 — Eke verified other VSRAM addresses have no effect | inert both ways; and pair 19 does not exist in H32 |

**No documented behaviour makes plane A worse. The premise the owner bought holds.**

There is a corroborating detail in the *existing* measurement that nobody has pointed at yet, and
it is the best evidence we have that the AND model is the right one for our ROM. The 2026-08-27
reproduction found the sliver rendering at **V-scroll ≈ 0**, wiping the ground. Under the AND
model that is exactly what should happen here: plane B is locked at 0 with a small wobble, so
when the wobble sample is a small positive number, `camY & 7` (say) is near zero — while a
*negative* sample is `$FFFx`, whose AND with camY is ≈ camY, i.e. nearly correct. That is why
scene 11 was "not at this sample": the artifact's visibility oscillates with the sign of the
wobble. The measured signature is a prediction of the AND rule, not just a fact consistent with it.

### The price, corrected

**`d-40` priced this as "it costs the background layer its wobble on its rightmost 16 pixels".
That understates it, and the understatement is structural, not a rounding.**

Column-pair 19 is also the entry that renders the right edge (§1). After the borrow, plane B's
rightmost 16 px render at **plane A's V-scroll**, not at plane B's value minus a wobble sample.
And in this game's per-column scenes plane B is vertically **locked**: `rocking_scene` and
`perspective_scene` both author `v_factor: 15, v_offset: 0`, which is Step 5's lock sentinel, so
`Parallax_Current_Vscroll_BG = 0`. Plane A carries camY — 144 at the boot area, 461 in the state
the owner captured. So the displacement is `camY mod PLANE_B_SPAN` = camY mod 512, arbitrary and
large, **not** the loss of a ±few-pixel wobble.

In plain terms: a 16-px-wide, full-height strip at the right edge of the screen showing the
background at a different vertical position. It is visible only through plane A's transparent
pixels, which in a side-scroller is mostly sky — but it is there on every per-column scene, at
every camera position, permanently.

**Why 16 px and not fewer: the two costs are conserved.** Plane B's share of pair 19 is
`16 - shiftB` px on the right, and if plane B's HScroll were misaligned its own leading sliver
would take the other `shiftB` px on the left (also at the AND value = camY). Sixteen pixels of
plane B pay for the fix no matter how they are arranged. With `shiftB == 0` — which is what
`fb: FACTOR_0` over `DeformTable_Zero` gives on the Rocking family — all sixteen sit on the right.
Perspective's shimmer rows have a live `dsb` on the hills and floor layers, so on those rows the
sixteen split between the two edges.

**Why it is unconditional.** Gating the write on `plane-A HScroll & 15 != 0` would skip it at one
camera X in sixteen (where there is no sliver to fix) and hand plane B its correct right column
back for that one position. That makes a 16-px background strip blink in and out once every 16 px
of camera travel. A steady seam reads as deliberate; a blinking one reads as a bug. Recorded so
the next reader does not "optimise" it back in.

**There is no cheaper value.** The requirement is that `A19 & B19 == camY`, i.e. B19 must be a
bitwise **superset** of camY in the bits the plane uses (low 9, since `PLANE_B_SPAN` is 512). The
smallest such value is camY itself; every other choice (`camY | bgV`, `$03FF`, …) displaces plane
B at least as far. Splitting the damage between the planes is possible in principle —
`A19 = camY|X`, `B19 = camY|Y` with `X & Y == 0` also yields camY — but every split moves damage
onto plane A's own right edge, which is the foreground. Derived, not measured.

### Where this leaves the ruling

The owner ruled for this fix on a description of its cost that was materially too small. That is
the same failure `d-27` had, and the triage says so in as many words about `d-27`. **This lane's
position: land the fix (it does exactly what he asked, and it is the only option that removes
rather than hides the artifact), and put the corrected price in front of him with the ROM in
hand, because the right-edge seam is a thing to LOOK AT, not to adjudicate on prose.** If he
looks at it and prefers the old artifact, the revert is the same one instruction.

---

## 5. What this does to `SceneLeftColMask`

The declaration family in `engine/level/scene_dsl.emp` offers `Factor0Lock` (verified: the
artifact cannot occur), `Accept` (ship it — what Gynoug did), and `SpriteMask` (refused until its
emitter lands). Post-borrow:

- **`Accept` no longer means what it says.** The engine does not ship the plane-A artifact any
  more, on any scene, regardless of what the scene declares. What a per-column scene now accepts
  is the *residual*: plane B's 16 px. The banner and the guard messages are rewritten in this
  parcel to say that, because a declaration whose name is false is the exact failure this parcel
  was also sent to clean up.
- **`SpriteMask` is what the owner rejected.** `d-40` offered him the bar and he said no. Its
  refusal message now cites that ruling rather than pointing at an emission parcel as though it
  were merely pending.
- **`Factor0Lock` survives with its five guards intact and unchanged**, and it is now the only
  arm that describes a *different* runtime: a scene with both planes' HScroll locked has no
  sliver on either plane — but it still pays the 16-px seam, because the borrow is unconditional.
  That is a wart, it costs nothing today (zero scenes declare `Factor0Lock`; the census in
  `effects_budget_check` reads `Accept:2, SpriteMask:0, Factor0Lock:0`), and it is booked rather
  than papered over.

**Recommendation, and it is a recommendation with a decision procedure rather than a pick.** The
family's whole purpose was to force an answer to a question the engine could not answer. The
engine can now answer it, uniformly, and no scene can choose otherwise — so the *structurally*
right end state is to **retire the family**: the enum, the `sc_left_col_mask` field, the mandatory
ensure, the five guards, the two poison modules, the axis-5 `SpriteMask` budget rows, the six
`Accept` spellings, and the Aurora-side schema key that `tools/effects_gen.py` accepts.

**This lane did not execute that, deliberately, and the reason is the corrected price above.**
Retiring `Accept` is only right if the plane-B seam is acceptable, and nobody has looked at it.
If the owner sees the right edge and rejects it, the fix becomes per-config — which needs a
config-record flag, a byte-moving paired landing — and `Accept` comes straight back as "decline
the borrow". Deleting an authoring surface and a cross-repo schema key the day before we might
need it back is not cleanliness, it is churn. So:

> **After the owner has seen the right-edge cost:** if he accepts it, retire the family in one
> parcel (cross-repo: Aurora's scene schema owns the key too). If he rejects it, the borrow
> becomes per-scene and `Accept` is live again with a real mechanism behind it. Booked in
> `docs/DEFERRED_WORK.md` under this parcel's entry.

Rejected alternatives, with reasons: **a new arm naming the fix** (`VsramLatch` or similar) —
rejected because with the borrow unconditional, such an arm cannot change anything, and a
mandatory declaration with one available answer is ceremony that reads as coverage. **Keeping
`Accept` with its old meaning** — rejected, its name would be false. **Making the borrow opt-in
now** — rejected as out of this parcel's scope (a config-record change is a byte-moving pair,
and it would be adding a knob nobody has a reason to turn until the seam has been looked at).

---

## 6. TAGs — what the controller should run, and what a pass looks like

This lane has no emulator. `tools/fg_left_edge_probe.py` is the closest instrument and, as the
triage already recorded, **it has no scene selection**, so as written it samples the boot scene
with reg `$0B` bit 2 clear. `tools/fg_left_edge_gate.py` (added by this parcel) is the scene-aware
version; §7 of this document's companion — the gate's own header — states its poison.

**TAG 1 — the fix, on plane A.** Scene 12 (`Rocking Fast`; loudest of the six and not
phase-dependent like scene 11), at a camera position with ground continuous across the screen.
Read reg `$0B` bit 2 **at the sample point** (the DEBUG warp clears it and travelling re-applies
the section's scene — both manufactured a false negative on 2026-08-27). Sample plane-A `opaque`
across x = 0, 8, 16, 24 over ground rows.
**PASS: every column opaque, x=0 behaving like x=16.** That is the owner's symptom gone.

**TAG 2 — the price, on plane B, and this is the one he will ask about.** Same scene, same
camera. Sample plane **B** at x = 288, 296, **304, 312** across a band of rows, and compare
against x = 0..280. Predicted: the two rightmost 8-px cells show background content from a
different vertical position — displaced by `camY mod 512` relative to their neighbours. Expect a
visible vertical seam at x = 304 wherever plane A is transparent. **This is expected behaviour,
not a regression** — but it is what the owner is buying, and he has not seen it.

**TAG 3 — the honest A/B.** Same two captures on the pre-parcel ROM. The left edge should be
broken and the right edge clean; after, the reverse. Anything else means one of the two models in
§1 is wrong about our ROM.

**TAG 4 — the extent, if it is cheap.** Under GPGX/hardware the pre-fix damaged strip is
`(-camX) & 15` px wide and sweeps with camera X; under Oracle it is a flat 16. Sampling the
pre-fix left edge at two camera X values 8 px apart would show which model our instrument is
running. It does not change the fix; it would settle whether our own tree should stop saying
"16 px".
