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

## 8. The universal countermeasure: inversion

Every trap above was either caught by, or is best defended by, making the guard fail on
purpose: flip the predicate false and watch the build go red; perturb the pinned constant
and watch the gate fail; poison the fixture and watch the sentinel fire. A green you have
never seen red is not evidence. (See also `docs/DEFERRED_WORK.md`'s vacuous-gate history —
this tree's most expensive lesson, learned more than once.)
