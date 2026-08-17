# ADJUDICATION — effects-tail r3 MINI-SWEEP (two seats, 2026-08-17)

Subject: the five adjudication-minted mechanisms in r3 (flagged `[minted]` there) — the only
parts of the design no adversarial eye had seen. Seats: **M1** minted-mechanism feasibility
(Fable), **M2** whole-document coherence + gate completeness (Sonnet).

12 findings. **12 ACCEPTED, 0 rejected.** All are patch-level against r3 — no structural
revision; r3 is amended IN PLACE (r3.1) in the same commit as this document.

## The convergent finding (M1-F1 + M2-1): `resolved_rec[]` is deleted

The two seats hit the same slot array from opposite directions:

- **M1-F1 (CORRECTNESS)**: the resolver's suppress paths write `resolved_ch` only — a
  record slot not written this pass retains the value from TWO frames ago (the last publish
  into that same bank). Concrete: frame N emits fl 200 into bank A; frame N+1 suppresses,
  publishes into bank B whose rec slot still holds frame N-1's 199; the builder reads 199,
  `prev < 199 <= 222` PASSES the backstop (in-range by construction), and the tint is
  emitted on a row the parallax — reading `resolved_ch = SUPPRESSED` — says is dry. Palette
  and scroll diverge: the exact class Parcel W removed and the suppress rule exists for. The
  backstop cannot catch it.
- **M2-1 (CONTRADICTION)**: statics never write `resolved_rec[k]` at all (the static path
  publishes nothing), so §A5's literal "builder reads `resolved_rec[k]`" has every static
  read 0 and fail `prev < L` forever — statics suppressed as a class, the thing the whole
  design exists to forbid.

**Disposition: ACCEPT both; fix = M1's option (b), delete `resolved_rec[]`.** The builder
already decodes the channel index from `line_src` (`raster.emp:1130-1131`) and GUARD 11
makes channel→record unambiguous, so patchable records read `resolved_ch[ch]` directly;
statics keep today's untouched literal path (`bpl .have_line`) and never touch the bank.
`resolved_ch` is TOTAL per publish over channels-with-records (every resolver path writes
it: a line or SUPPRESSED), and channels without records stay NONE in both banks via the
install reset — no stale-slot class exists. RAM: 50 → **18 bytes** (2 banks × 4 channel
words + selector). Simpler, smaller, and it closes r3's open item 5 outright (statics can
no longer even reach a bank read).

## Remaining dispositions

| # | finding | verdict | r3.1 action |
|---|---|---|---|
| M1-F2 + M2-5 | The spacing word MOVES THE TRAILER (+2): `ship_trailer` is emitted immediately after the patch table (`raster_dsl.emp:1771-1772`). Unenumerated readers: `Raster_InstallPatched`'s trailer-offset arithmetic (`raster.emp:949-954` + comment `:934-935`) — misreading it corrupts the ship entry of the ONLY shipped patchable config; `Raster_GetChannelBand`'s walker (`raster.emp:1237-1246`); `patched_words` (`raster_dsl.emp:1751-1752`); `check_rec_layout`'s entry index (`:1719`). Bonus rot found: `raster_dsl.emp:1623` says "8*records" — ALREADY stale (records are 10 bytes) | ACCEPT | full reader enumeration replaces §A5's single `addq` sentence; the stale `:1623` comment fixed in the same commit (it is the copied-number class the change would trip over). Verified clean by M1: sigil carries NO table-offset pins (symbol pins only), `effects_gates.py`'s indices are live-buffer arm words the table header never enters — D2-3's dissolution CONFIRMED sound |
| M1-F3 | Header word order unpinned; adjudication and r3 lean opposite ways | ACCEPT | **pinned: `[count][spacing]`** — count stays word 0, so `Raster_InstallPatched`'s count read and `Raster_GetChannelBand` keep their entry shape and the +2 confines to the record-walkers and the trailer offset |
| M1-F4 | "reset is `clr` × 3 words" understates the reset; clearing only the selected bank re-opens the stale class; ordering (clear BEFORE the install call) only implied | ACCEPT | reset = BOTH banks + selector, fully (18 bytes, 5 `clr`-class stores); ordering constraint stated: banks clear beside `preset.emp:220`, strictly before the install call that publishes into one of them |
| M1-F5 | Install-site register plumbing feasible but unstated: the call goes after `lea RASTER_BUF_SIZE(a0), a1` (`raster.emp:930`) and before the `:931` store; a0 is dead after `:930`; the resolver must fit `clobbers(d0-d4/a0-a2)` (the register budget is exactly exhausted — a1 round-trips the call on the stack) or the declaration widens up the chain (the d5 precedent) | ACCEPT | stated in §A5; the clobber ceiling is a design constraint on `Raster_ResolveLines`, named as such |
| M1-F6 | "carriers live through the ordinary repin" true for address pins, NOT the `parallax_port.rs` stub table — removing the parallax call is a HAND edit to the outbound-stub list, in the same change that adds `Effects_Resolved_*`/`Sel` stubs | ACCEPT | §A5 cross-seam paragraph corrected |
| M2-2 | D2-1's unsoundness class has NO witnessing poison: the enumerated G-A3 poison is two-record, which a regressed single-`prev_hi` walk still refuses. An implementer reverting to "extend check_intervals" passes every listed poison | ACCEPT | new poison: THREE records — two same-side patchables with non-monotonic `band_hi` (`P_wide`, `P_narrow`) then a static — refused by the full scan, wrongly admitted by a prev_hi chain |
| M2-3 | D1-9's forward-walk density fix has no witnessing poison: "static-patchable at gap 1" is the `i,i+1` pair even a naive check catches | ACCEPT | new poison: `(S1, P, S2)` with S1↔S2 a density violation only a forward walk past P can see |
| M2-4 | The two resolver call sites + RAM widening + parallax consumer switch + sigil declarations are a FORCED ATOMIC LANDING: staging the main-loop site before the install site reproduces D1-1's regression exactly, and r3's own install-crossing gate would be red on the intermediate commit | ACCEPT | §A7 gains an explicit atomic-cluster statement; the plan must treat it as one landing (single-op landing discovery precedent, Parcel R1) |
| M2-6 | Double-resolve on crossing frames (install site + the same frame's per-frame site) never discussed | ACCEPT | stated: idempotent (same latch, `preset.emp:247` precedes both), one extra walk + flip; crossing frames pay the envelope twice. Benign — documented so nobody "fixes" it |

## Verified correct (carried as premises, selected)

- **Resolve-inside-install ordering HOLDS** (M1 #5): walked preset `:220` clr → banks clr →
  latch `:247` → install `:288` (resolve → flip → table store); a VBlank before the store
  sees table 0 → `.none`; after it, the bank is this frame's latch. Nothing between resolve
  and store touches the banks (`Build_DMA_Entry` writes `Static_Pal_Ship` only).
- **No static can fail the backstop under coherent banks** (M1 #2): earlier patchables emit
  ≤ their own `band_hi_fl` ≤ `S_fl - spacing`; earlier statics by `fire_lines` ascent; the
  shipped adjacent-static zero-gap case (`RASTER_BAND_TWIN_SH1`, fl 138/139) passes strict
  `prev < L` and stores gap byte 0. With `resolved_rec[]` deleted the question is moot —
  statics never read a bank.
- **Sentinel arithmetic sound end-to-end** (M1 #3, M2): [2,222] emit range verified from
  `patchable` bounds; push cannot output below 2; the builder needs no sentinel test —
  `prev < L` with prev seeded 1 rejects 0 and 1 arithmetically (now that `resolved_ch` is
  total, the premise holds).
- **Reset topology closed** (M1 #6): the only runtime callers of both installers are
  `Effects_InstallPreset`; teardown paths run over already-cleared banks; the
  table=0-with-stale-banks window does not exist today, and r3's ensure guards the future
  caller.
- **Per-frame site ordering matches the shipping loop** (M1 #7): latch → CheckBoundary →
  Update (`ojz_scroll_test.emp:322/:377/:492`), consistent with `raster.emp:1270-1275`.
- **G-A6's 676 re-derived independently** (M1 #8) from the pinned model constants,
  cross-checked against the F1/F4 pins; ceil(676/488) = 2.
- **M2 whole-document pass**: sentinels used consistently across §A2/§A4/§A5/§A7; RAM figure
  internally consistent; G-A3/check_density coupling correctly stated; backstop placement
  verified against `.suppress` bookkeeping; priority-welding verified against all three
  guards; every checked line cite matched source.

## Process note

The `resolved_rec[]` deletion is again an adjudication-SELECTED fix — but unlike the r2
round it is seat-PROPOSED (M1's own option b), and the second seat's independent finding
(M2-1) is resolved by the same edit. Both seats' reasoning covers the chosen shape. The
residual risk is rated low and the implementation plan's collision-scene gate exercises the
exact suppress-then-read path M1-F1 describes.
