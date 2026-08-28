# `.emp` Pitfalls — Measured Traps in the Sigil Language

Every entry here was hit live in this tree, with a date. These are not style rules
(see `CODING_CONVENTIONS.md` for those) — they are places where `.emp`/sigil behaves
in a way that produces **silently wrong output or misdirected diagnostics**. Read this
before writing any nontrivial comptime code, and re-read the relevant entry before
trusting a guard you just wrote.

The recurring theme: **the failure mode is silence.** Where a diagnostic exists it often
points at the wrong site. The universal countermeasure is inversion: make the thing fail
on purpose (flip a predicate, perturb a constant, poison an input) and confirm the build
goes red before you trust the green.

---

## 1. Nested if-expressions silently yield unit `()`

**Trap:** an `if` in block-tail position evaluates to nothing. Single-level
if-expressions work; nesting one inside another's `else` block returns `()` with **no
diagnostic** (measured twice independently, 2026-08-18, scanline P1):

```emp
comptime fn NEST(a: int, b: int) -> int {
    return if a == 1 { 1 } else { if b == 1 { 1 } else { 0 } }
}
// NEST(1,0) -> 1   ok
// NEST(0,1) -> ()  WRONG
// NEST(0,0) -> ()  WRONG
```

This silently folded a scene capability mask to 0 — a wrong specialization decision with
no build error. A *call* in block-tail position is fine (verified).

**Rule:** for bit accumulation, use a flat accumulator over *statement* ifs:

```emp
comptime var acc = 0
if a == 1 { acc = acc | BIT_A }
if b == 1 { acc = acc | BIT_B }
return acc
```

## 2. Comptime-helper imports don't travel to call sites

**Trap:** a `comptime fn`'s free names resolve at its **call site**, not in its defining
module. In a `COMPTIME_HELPERS` module (raster_dsl, palette_dsl, vdp, …):

- names **defined** in the module (`pub const`, `pub comptime fn`) are glob-injected and
  resolve everywhere — safe;
- names **imported** via `use` are module-local and do **not** travel. Naming one in a fn
  body breaks at every call site — **silently** (hit live 2026-08-14: a range spelled
  with two imported constants collapsed to empty, the fn returned zero results, no error).

Quick diagnostic: interpolate the name in an `ensure` message — it prints `<?>`.

**Rule:** inline the literal in the fn body and hold it with a module-level `ensure` pin
against the imported constant. This is why DSL bodies spell `2`/`$8AFF`/`3..224` rather
than named constants — it is deliberate, not sloppiness.

## 3. Guards in unreachable modules are dead — parse ≠ evaluate

**Trap:** sigil parses every module in the manifest but only **elaborates** those inside
the target's `use` closure. In an unreachable module: `ensure` never fires, declared
`struct (size: N)` layouts are never validated, and even undefined names in a fn body
build green with an unchanged CRC (all measured, 2026-08-14/18). Parse + scan coverage,
**zero body-elaboration coverage**.

Also NOT reachability: a `map.toml` `order` row (placement if lowered, not lowering), and
an unreferenced top-level `const X = f(...)` (comptime-inert — proves nothing). And an
`ensure` comparing an imported DATA symbol to an integer is unevaluable and
**silently always-passes** in both polarities — never reach for that shape.

**Rule:** after adding any guard-bearing module, run
`SIGIL_WARNINGS=full DEBUG=1 ./build.sh 2>&1 | grep module.unreachable` — sigil names
every unreachable module and counts its dead ensures. Baseline 2026-08-18 (sonic4 DEBUG):
25 modules / 63 dead ensures, all explained (poison fixtures, seam-lowered Z80/sound
data, other-target modules) — a NEW name in the list is a real signal. Then still
red-first at least one guard in the module: reachability is necessary, not sufficient.
Do not `use` a module merely to silence the warning (the warning text says so itself);
a zero-emitting witness module becomes reachable via a whole-path `use` from an
already-placed module.

**That baseline COUNT is stale and should be treated as a shape, not a number:** measured
again 2026-08-28 (sonic4 DEBUG) the list is **45 modules** before that day's band-ownership
parcel and **50** after it, and every name is still in the two explained classes (37 poison
fixtures, 12 seam-lowered Z80/sound, `games.demo.constants`). Nobody re-baselined it as the
poison directory grew, which is exactly how a "a NEW name is a real signal" rule goes quiet.
Compare NAMES against a run on the same tree without your change, not the count against 25.

## 4. `d0`–`d7` / `a0`–`a7` are register tokens — even in comptime code

**Trap:** `let d0 = 5` in comptime code binds a **register**, not an int. Passing it on
fails with `a register is not a valid int argument`, and the diagnostic points at the
**call site**, not the binding — the blamed line is innocent (hit 2026-08-18 naming
per-layer deform shifts `d0..d3`).

**Rule:** never use register spellings as value names; pick a non-register spelling
(`dsa0..dsa3`). If a confusing "not a valid int" error names an innocent site, grep the
argument chain for register-token names first.

## 5. `extern()` poisons comptime-ness

**Trap:** `extern("Sym")` yields a link-time value that folds in some positions and
breaks others, always as `here.provisional` errors pointing at an **unrelated file**
(both measured 2026-08-15). It does NOT work: (a) in a module-scope `ensure` inside a
COMPTIME_HELPERS module (the glob-injected guard evaluates inside other modules'
instruction streams); (b) folded into an emitted data image that a comptime pin then
compares — the whole image becomes non-comptime and the pin breaks, in every spelling
tried. It DOES work as a plain consumer-side `equ` at module scope in an ordinary module
(`buffers.emp`'s `SRC_PAL_LINE0` is the worked example).

**Rule:** carry PARAMETERS (offsets, counts, base-relative addresses) in emitted data and
add the absolute base at **runtime**. This is usually the better design anyway — it
removes consumers that know another module's byte layout.

## 6. `assert.<w>` — three traps around a good mechanism

`assert.<b|w|l> src, cond [, dest]` is a language builtin: full-SR save/restore
(CCR- and IPL-transparent), self-gates to zero bytes when `DEBUG != 1` (undefined
`DEBUG` is a hard error), fails onto the MD Debugger screen with an auto-message.
Surrounding setup instructions do NOT self-gate — wrap them in `if DEBUG == 1 { }`
yourself, and prove zero release cost by CRC equality, not reasoning.

- **Trap A — `[context.escape]`:** an assert may not sit inside `with z80_stopped { }`
  (its raise rail is a modelled tail-out). Hoist it outside the `with`.
- **Trap B — IPL is not uniform:** the main loop idles at IPL 3, VBlank context is
  IPL 6, hand-masked spans are IPL 7 — so `eq, #$0700` is usually wrong. "No VBlank can
  land here" is `hs, #$0600`. (`move.w sr, dN` is fine on 68000 supervisor and does not
  trip `[proc.sr-undeclared]` — that fires only with SR as destination.)
- **Trap C — sonic4 can build green over a broken tree:** shape-gated brackets like
  `with z80_stopped if SOUND_DRIVER_ENABLED == 0` mean the failing region may only be
  planted in `demo`. **Always build all four shapes** (sonic4/demo × plain/DEBUG).

Placement: never immediately after the proc's own `move.w #$2700, sr` — that asserts the
line above it and is vacuous.

## 7. Address-register destinations: spell `adda`/`suba`/`cmpa`

**Trap:** the emp frontend was measured (2026-08-12) encoding `add.w dN, aM` as ADDX
garbage — a memory-corrupting wrong opcode, not an error. Sigil-side hardening was
delegated to its own lane; the house spelling is explicit `adda.w`/`suba.w`/`cmpa.w`
regardless, and it is what keeps the tree clear of the hole.

**Rule:** never write `add`/`sub`/`cmp` with an address-register destination in `.emp`.
When an effect "fires but nothing changes," disassemble the built ROM bytes (capstone)
before trusting the source.

## 8. A struct declaration is re-elaborated in every module that IMPORTS it

**Trap:** importing a struct pulls its *declaration* into the importing module's name
environment, so every name in its size annotation and in its array lengths must resolve
THERE too — including names the importing module never spells. A partial import fails
**pointing at the declaration**, in the defining file, naming a type that file plainly
declares (measured 2026-08-20, scanline P3 Task 8):

```
[Error] unknown type: band_entry @ engine/level/parallax.emp   <- the file that declares it
[Error] expected an integer, got label                          <- a const the same file declares
```

Forty of them from one missing name in one `use` line, all blaming an innocent file. The
declaration itself was correct and built green in isolation.

**Rule:** when a struct's declaration names helpers (`sizeof(other)`, an extension struct, a
count const), import the WHOLE set everywhere the struct is imported, and say so at the
declaration. Diagnosing this from the message alone is close to impossible — the reported
site is never the broken one.

## 9. Contract members (`Game.*`) do not exist in layout or harvest contexts

**Trap:** `Game.SCANLINE_CAPS` folds fine in a proc body and in an ordinary module-scope
`ensure`, so it reads as generally available. It is not. Three contexts have no contract
binding at all (each measured 2026-08-20):

- **the layout of an emitted `data` binding's record type** — `unknown name
  Game.SCANLINE_CAPS`, once per emitted record;
- **`harvest_engine_struct_offsets`** — the ambient `STRUCT_OFFSET_TWINS` layout is one file
  plus `types.emp`, no profile, no defines, no contract. A `Game.*` in a harvested struct's
  size expression kills the build before a byte is emitted;
- **`harvest_engine_ram_addresses`** — the focused `use engine.ram`-only build, so
  `engine/ram.emp` cannot size a reservation by capability either.

Inside a **`comptime fn` body** it is worse than absent: it degrades to a LABEL (`` `&` not
defined for label and int ``), which is the section-2 call-site-resolution rule biting a contract
member.

A **build define IS visible in all three** (`DEBUG` sizes a struct correctly and builds
byte-identically), which is the shape of the fix: an `emp_defines` row per game, the
`MAX_RING_BUFFER` pattern, cross-pinned to the contract member in a module that can see both.

**Rule:** anything a LAYOUT depends on must come from a define, a literal, or a same-file
const — never from `Game.*`. If the value is genuinely a per-game contract member, carry it
as a pinned mirror and put the two-directional `ensure` in a module where both names are
visible (`games/sonic4/data/effects/scene_registry.emp` is the worked example) — and book
the define, because one engine constant cannot serve two games that disagree.

## 10. The universal countermeasure: inversion

Every trap above was either caught by, or is best defended by, making the guard fail on
purpose: flip the predicate false and watch the build go red; perturb the pinned constant
and watch the gate fail; poison the fixture and watch the sentinel fire. A green you have
never seen red is not evidence. (See also `docs/DEFERRED_WORK.md`'s vacuous-gate history —
this tree's most expensive lesson, learned more than once.)

## 11. ~~Unsized `lea ROMTable, aN` can mis-measure a whole section in the placer~~ — SYMPTOM REAL, MECHANISM REFUTED, WORKAROUND SUPERSEDED

**Read the correction first; the original text below is kept only because the SYMPTOM is worth
recognising.** This entry was written 2026-08-26 from the ring-sparkle parcel and its stated
mechanism was WRONG. The sigil lane reproduced the symptom exactly — 7 `nop`s in
`RingCollision` on bare master, `player_sensors` measured 0x4DC vs 0x4F4 packed, the same 24 B
at the same twelve `lea` sites — and then refuted the explanation:

- **What this entry claimed:** the provisional measuring round encodes `abs.w` because the
  target's address "is still unknown".
- **Why that cannot be true:** an unresolved operand is a HARD ERROR in sigil, not a width
  guess. Those tables are `abs.l` at the provisional pin too.
- **The actual cause:** the collision-fallback SCRATCH SLOT wraps the 24-bit bus.
  `collision_data` landed at scratch slot 41 = `0x300_0000`; the width rule masks to 24 bits,
  giving `0x0`, and at THAT address `abs.w` is a legitimate encoding. The section measured
  short because it was measured at an address that aliases zero — nothing to do with the pin
  being provisional, and nothing to do with how the `lea` is spelled.

**Consequence for style:** the explicit `lea (Table).l, a1` / `movea.l #Table, a1` spelling is
a WORKAROUND that has been superseded, not a standing rule. Sigil's fix (`fix/measure-at-packed-base`)
makes every measuring round exact at its own bases and deletes the scratch/spread fallbacks, and
adds a loud non-convergence diagnostic naming any width-flipping site with both encodings. Keep
an explicit width where you want a particular cycle shape; do not add one "for the placer".

**What survives, and it is the useful half:** when the placer names a pair of sections that
nothing in your change touched, the fault is in how one of them was MEASURED, not in the map,
and not in the innocent pair it named. That instinct is right even though this entry's account
of the measurement was not.

**Lesson about the entry itself:** a mechanism reasoned from a correct measurement and a
plausible story still needs the other repo's owner to check it. The measurement (24 B, twelve
sites, reproducible) was sound and is what let sigil find the real cause quickly; the causal
story attached to it was invented here and would have propagated as a style rule for the whole
codebase. Report the measurement to the owning lane; let them supply the mechanism.

---

*Original text, superseded 2026-08-26:*

**Trap:** sigil's `packed_true_bases` walk measures each section once at a PROVISIONAL base
before the real one is known. An unsized `lea Table, aN` to a ROM table whose provisional
address is still unknown encodes **abs.w (4 B)** in that round and **abs.l (6 B)** at the
real base. Twelve such sites in `player_sensors` (`probe_core` x4) measured the section 24 B
short; the walk placed the next section 24 B into it, and the build died with
`packed layout overlaps at its real bases — a run grew into a declared anchor ... sections
section [..] and player_sensors [..] overlap` — **naming an innocent pair**, and only once
upstream growth passed the slack (+2/+6 B built; +14 B — seven `nop`s on bare master — did
not). Measured 2026-08-26 (ring-sparkle).

**Rule:** a `lea`/`move` to a ROM label that lives above `$8000` (every data table) is spelled
with the explicit width — `lea (Table).l, a1` — or as an immediate `movea.l #Table, a1` when
the operand is a template argument (`({ptable}).l` does not parse). Same 6 bytes, same
cycles, base-invariant measurement. When the placer names a pair that has not changed,
suspect a width choice in the EARLIER section of the pair before suspecting the map.
