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

**AMENDED 2026-09-02 — the trap is NARROWED, not closed.** Sigil now refuses a comparison
whose operands are of different kinds (§12), and a folded `()` meeting a value of any other
kind is such a comparison. So the fold is caught **at the comparison**, loudly, and the
refusal carries this section's guidance in its own text:

```
[Error] [eq.cross-type] `==` not defined for unit and int — … One operand is `unit`, which
        is a value nothing produced deliberately: a LIKELY cause is an `if` in value position
        whose taken branch yields nothing, which folds to `()` silently (see the `.emp`
        pitfalls, §1 — the silent unit fold). Check what produced the `unit` side; `unit` has
        other sources, so treat this as a lead rather than the answer
```

**Read exactly what moved, and do not read this entry as fixed.** Three things are still true:

- **The fold itself is still silent.** A block-tail `if` with no `else` still evaluates to
  `()` and sigil says nothing *where the `()` is produced*. Measured 2026-09-02 on sigil
  `6a8b3ecd`: the `NEST` shape above, reproduced in a throwaway probe and called as
  `NEST(0,0)` against an int, produced **exactly one** `[Error]` — the comparison's. Not
  two. Nothing was reported at the fold.
- **A `()` that is never compared is still silently wrong.** The refusal is a property of
  `==`/`!=`, not of the fold. A folded `()` that flows into a mask, a length, an emitted
  record or another fn's argument reaches none of this machinery and is exactly as silent
  as it was before. Whether the wrong specialization this entry records went that way or
  through a comparison was not re-established; assume nothing about your own fold.
- **The hint is a lead, not a verdict.** It says *likely cause* because the compiler has
  established the operand's KIND and nothing about its provenance; `unit` also comes from an
  empty `else`, a statement used as a value, and a fn falling off its end.

The differential-twin `ensure` this entry used to require is therefore a belt-and-braces
measure rather than the only surface — but the flat-accumulator rule above is unchanged, and
it is still what prevents the fold instead of catching it.

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

## 12. Comparing two things that can never be equal — the always-RED guard

**Trap:** comptime `==`/`!=` used to be **total** — any two values of different kinds were
"simply not equal", with no diagnostic. That reads as permissive; it is the opposite. It
turns a mistake into a **constant**, and a guard built on a constant is not a guard. It has
two signs, and both were hit live:

- **always RED** — a bareword naming a `pub data` symbol resolves to a LABEL, so
  `ensure(first_mismatch([Variant_Water_Deep], [variant(shift_r: 1, shift_g: 1)]) == -1, …)`
  compared a label against a struct, was always unequal, and reported a mismatch for the
  twin that AGREES. No value of either side could have made it pass;
- **always GREEN** — two different struct types compared FALSE rather than refusing, so a
  typo'd constructor read as an ordinary mismatch instead of a type error.

Both shapes are the sigil lane's measurements of the OLD behaviour (item-5 comptime probe),
carried across rather than re-run here — the pre-change compiler is not available to this
tree. Everything below was re-measured against `6a8b3ecd` on this tree.

Since 2026-09-02 (sigil `6a8b3ecd`) equality is defined **within a comparison class** and
**refuses across classes**, so both signs are now build errors:

```
[Error] [eq.cross-type] `==` not defined for struct `pal_variant` and int — no value of one
        can equal a value of the other, so this comparison is always false; compare
        same-typed values (or their fields)
```

Aggregates recurse, so the refusal lands whether the values meet directly (`[a] == [b]`) or
one element at a time inside a helper like `first_mismatch`.

### The two cross-kind comparisons that stay DEFINED — read these before writing a workaround

Everything else across classes refuses. **These two do not**, deliberately. Refusing either
would fire on correct code all over this repo's effects tables, so if you meet one, it is
not the trap and it needs no workaround:

1. **A label beside `0`.** `0` is how `.emp` spells an absent symbol in a pointer slot —
   `preset(variants: [Variant_Water_Deep, 0])` is the ordinary spelling of "one variant, the
   second slot empty", and every OJZ preset carries it. A real label is never `0`, so
   `slot == 0` is always false and is still the emptiness test you want. Measured on
   `6a8b3ecd`: `preset()`'s own live guard `ensure(raster == 0 || patched == 0, …)` fired
   with **its own message** when handed a real label in both slots (an ANSWER of false, not
   a refusal), and `variants: [Raster_Program_None, 0]` builds clean.
2. **A newtype or `fixed<>` value beside a bare int.** This is the language's erasure rule
   (`empyrean/docs/SIGIL_SPEC2_LANGUAGE.md` §4.1/§8.3 — newtypes, `fixed<>` and refinements
   are erasing; **not** this document's §8) and it predates the change. Measured:
   `Angle(5) == 5` is true and `Angle(5) == 6` is false — it answers,
   in both directions. Two DIFFERENT newtypes do **not** compare:
   `Angle(10) == GridX(10)` refuses with ``[eq.cross-type] `==` not defined for newtype
   `Angle` and newtype `GridX` ``.

**One asymmetry, measured here and easy to trip over:** the `0`-means-empty spelling lives in
`[Label; N]` array slots and in parameter DEFAULTS. An explicit bare `0` passed to a
**scalar** `Label` argument is refused — ``expected a label (a `Label` argument), got int`` —
by an argument-kind check that is **not** `[eq.cross-type]`. Same keyword, different
mechanism; do not diagnose it as a comparison problem.

**DATED 2026-09-02: this asymmetry is OLD and has nothing to do with the equality change.**
The same probe — a `comptime fn` taking a scalar `Label`, called with `0` — produces the
**byte-identical diagnostic** on the pre-change compiler (`cdd330ff`) and the post-change one
(`6a8b3ecd`), and the `[Label; 2]`-with-a-`0`-slot half is accepted by both. So a reader who
meets this message has not found a side effect of §12 and should not go looking for one. Run
by the sigil lane and reproduced here independently against both binaries.

*How this nearly went unrecorded, because the lesson is about prohibitions rather than about
labels:* the pre-change binary was frozen read-only during the landing, and the freeze was
written — and read — as "off-limits". **It was `-r-xr-xr-x`: writing was refused, RUNNING was
never in question**, so the A/B was available the whole time at no cost and to nobody's risk.
A prohibition should say what it forbids and, where the distinction is load-bearing, what it
still permits; an over-broad one buys caution by deleting a measurement.

### The trap with teeth: the one-keystroke "fix" that makes the guard permanently vacuous

An always-red guard looks like a broken assertion, and the cheapest way to make it stop
shouting is to flip its constant — `== -1` becomes `== 0` and the build goes green. That
edit does not fix anything: it selects the *other* constant answer, and the guard is now
permanently vacuous with nothing left to notice. On a pre-`6a8b3ecd` sigil that is the whole
failure mode. Since `6a8b3ecd` the compiler refuses the comparison instead, which removes the
keystroke — **but only when the two sides differ by KIND.** A comparison that is constant
because you compared a value to itself, or to a copy of its own construction, still refuses
nothing and still needs §10's inversion.

Note also that the `unit`-operand hint (§1) says *likely cause*. `unit` has other sources —
an empty `else`, a statement used as a value, a fn falling off its end — so read it as a lead
about one operand's kind, never as a verdict about where it came from.

### The shape to reach for instead

Hold the value in a module-level `const` and feed BOTH the emitted twin and the guard from it:

```emp
const WATER_DEEP = variant(shift_r: 1, shift_g: 1)
pub data Variant_Water_Deep: pal_variant = WATER_DEEP
ensure(WATER_DEEP == variant(shift_r: 1, shift_g: 1), "water-deep twin drifted")
```

`WATER_DEEP` is a struct VALUE on both sides, so the comparison is in-class and the guard can
genuinely fail. Naming the `pub data` symbol was never comparing values — it was comparing an
address to a struct. (§3's related note still stands for the other direction: an `ensure`
comparing an imported DATA symbol to an integer at module scope is unevaluable.)

**Rule:** if a guard compares two things and you cannot name a change to either side that
would flip the answer, it is not a guard.

**Source.** The language-lawyer account — the full class table, the discrimination that
proved "always red" rather than merely "wrong", and the diagnostic's exact wording — is
sigil's `docs/EMP_PITFALLS_EQUALITY.md` §12, read at sigil
`3aa6f24028b0d4eed5d9602d4b4a0afee3bc06ea`.

## 13. A `comptime fn` signature's `[T; N]` is now a real length contract

**Trap:** a `[T; N]` annotation in a `comptime fn` signature used to check NOTHING. A
`[Label; 2]` parameter accepted a three-element argument and reported `v.len == 3`; the
return annotation was read by nothing at all. The wrong length surfaced only much later, when
a record built from the value was emitted — blamed on the **consumer's** `pub data` line:

```
[Error] array length mismatch: expected 2 element(s), got 3
        @ the whole `pub data OJZ_Preset_Sec3: EffectsPreset = preset(...)` line
```

That line is innocent; its author supplied none of the three elements. (The OLD behaviour and
that blame site are the sigil lane's measurement, carried across; the pre-change compiler is
not available to this tree.)

Since 2026-09-02 the length is checked at the signature — a parameter at the CALL, naming the
fn and the slot; a return at the fn that returned it. Both measured on `6a8b3ecd`:

```
[Error] array length mismatch: expected 2 element(s), got 3 — parameter `hand` of
        `probe_pair` is declared with a fixed length
[Error] array length mismatch: expected 2 element(s), got 3 — the return type of
        `probe_three` is declared with a fixed length
```

**Scope, deliberately narrow.** Array LENGTH only. A signature annotation still says nothing
about element TYPES, and a parameter still binds loosely when the argument is not an array at
all — so `hand: array` remains the way to say "any array", and `[Label; 2]` now means what it
looks like.

**Rule:** spell the length when you mean it. `-> [Label; 2]` is worth writing now, because it
fails at the fn that broke it instead of at whoever eventually emitted the result. (Sigil's
`docs/EMP_PITFALLS_EQUALITY.md` §13 at `3aa6f24028b0d4eed5d9602d4b4a0afee3bc06ea` for the
compiler-side scope.)
