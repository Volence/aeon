# Handoff — why does a plane B VSRAM write show nothing?

**Date:** 2026-08-14
**Branch:** `feat/effects-vsram-demo` (1 commit, `71b76e1f`) — **do not merge as-is**
**Master:** clean and green at `49c7ca9a`

---

## The one question

`vsram(2, [$0040])` — a mid-frame VSRAM write to byte 2, i.e. **entry 1 = plane B** — produced
**no visible change** in OJZ act 1 section 0, measured against a control build differing only in the
offset. The same program at byte 0 (**plane A**) produced a large, clean, correctly-timed change.

**Nobody has explained the plane B result.** That is the task.

Do not accept "it is probably occlusion" — that was the first guess, a layer-toggle probe was
inconclusive, and it was left explicitly unproven in the fixture comment and the gate evidence.

---

## What is already established (do not re-derive)

1. **The constructor works.** `vsram()` emits the right words; the build-time pin caught a wrong
   hand-derived command before the first run (`$4002 $0010`, not `$4000 $0002` — the address goes in
   the high word, the type bits leave `$10` in the low).
2. **The write lands on N+1.** Authored screen line 112 → first differing pixel row is exactly
   y=112, rows 108-111 pixel-identical. The DSL's existing `-1` needs no VSRAM-specific rule.
   Full method and numbers: `docs/benchmarks/effects-p3/GATE-EVIDENCE.md`.
3. **The VDP mode supports it.** Live shadow read: reg `$0B` = `$03` → HScroll mode `%11` (per-line),
   vscroll bit 2 = **0** = full-screen. So entry 0 is plane A and entry 1 is plane B, for every
   column. This is not a per-column-mode confusion.
4. **The program installs.** `Raster_Program` = `$00012F64`, `lookup_symbol` → `OJZ_TestVsram`.

## What was learned the hard way, and is a real engine constraint

**Mid-frame vertical scroll of plane A is unsafe in this engine.** `TILE_CACHE_ROWS = 60`
("viewport 28 + margin 16×2") — the margin around the camera window is the **streamer's working
area**, not display-ready content. Scrolling plane A down 64 px points the VDP at that scratch space,
so you get stale/half-written tiles: brown blocks, a grey rectangle, doubled art. The owner spotted
this from a screenshot before I did.

This is *why* the reference corpus writes VSRAM for plane B and not plane A, and it means the plane A
fixture on the branch renders corruption rather than an effect. **That fixture should not ship.**

---

## Candidate explanations, none tested

- Plane B's base vscroll is such that +64 px lands on self-similar content (the BG has strong
  vertical repetition — vertical trunk stripes are nearly translation-invariant vertically, which
  already defeated one measurement attempt).
- Plane B is largely occluded by plane A in this scene.
- Plane B's nametable is not populated in the region the shift reveals — the plane A problem in a
  different costume.
- `Vscroll_Write` or something else rewrites VSRAM[1] after the HInt within the same frame.
- The write is going somewhere other than intended.

**Suggested first move:** stop reasoning about visibility and read the value. Confirm whether VSRAM
entry 1 actually changes mid-frame. Oracle has no `read_vsram` MCP tool — that is the core
difficulty, and it is worth ten minutes deciding how to observe it (a `run_to_scanline` + framebuffer
probe on a scene where plane B is unambiguous; or temporarily disabling plane A *while the emulator
is running*, not paused; or a purpose-built probe scene).

---

## Environment and navigation — the expensive bits

```bash
cd /home/volence/sonic_hacks/aeon
export SIGIL_BUILD=/home/volence/sonic_hacks/sigil/target/release/sigil
export SIGIL_EMIT=/home/volence/sonic_hacks/sigil/target/release/emit_sound_blob
DEBUG=1 ./build.sh          # -> s4.debug.bin + s4.debug.lst
```

- **Oracle binary is `/home/volence/sonic_hacks/oracle/linux-port/build/oracle_gui`** (not under
  `emulators/`). Launch detached; **one instance only** — check with `pgrep -a oracle_gui`.
- **Load symbols** or every symbol-taking MCP op fails:
  `emulator_load_symbols('/home/volence/sonic_hacks/aeon/s4.debug.lst')` → 882 symbols.
- `emulator_press` leaves the emulator **paused**, and **the framebuffer does not re-composite while
  paused** — a layer toggle appears to do nothing until you advance (`run_to_scanline`) . This wasted
  a cycle.
- **Getting to a section.** `SECTION_SIZE = $0800` (2048 px, square); OJZ act 1 is a **3×3 grid**, so
  `section = (Camera_Y >> 11) * 3 + (Camera_X >> 11)`. Camera at `$FFA4B6` (X) / `$FFA4BA` (Y),
  16.16 fixed point.
- **Debug free-flight needs a cheat armed first.** B alone does not enter it — `debug_flag` stays 0
  and you are just moving the player under physics, hitting walls. Do not burn time on this; instead
  **bind the fixture to whichever section you can reach**, or to section 0 to see it at spawn.
- Fixture bindings live in `games/sonic4/data/levels/ojz/act1/act_descriptor.emp`
  (`raster:` / `cycle:` args to `ojz_sec`). Section 1 = P1 raster, section 2 = gradient,
  section 3 = cycling. Sections 4-8 free.

## The method that worked, and should be reused

**A control build differing in exactly one constant**, captured deterministically, then diffed
row-by-row:

```
reload_rom(path)            # full power-cycle reset
press(['start'], 150)       # same frame count both times
screenshot(path=...)
```

Then count differing pixels per row, **ignoring `y <= 24`** — the HUD ring counter differs run to
run and will otherwise mask the result. This is what produced the clean `y=112` answer; a naive
row-to-row difference on a single capture does **not** work, because the artwork is high-detail and
vertically self-similar.

---

## Standing constraints

- **Never `git add -A` or a path glob.** An auto-commit daemon owns uncommitted files under
  `games/sonic4/data/editor/` and `games/sonic4/data/sprites/`.
- This branch **moves bytes** (`fedcf197` → `79676d9c` plain). Merging requires the refreeze ritual
  (`refreeze --freeze <name> --ab <evidence>`) which permanently appends to the provenance chain —
  **the owner wants to sign that off**, it was deliberately not done.
- No real hardware. Oracle is the standard of evidence, and it is Exodus-derived (consults VSRAM
  continuously); GensKMod latches at HBlank start. Emulator disagreement on mid-frame VSRAM is a
  recorded known unknown.

## Outcome to aim for

Either **a plane B write that visibly works** — in which case retarget the fixture, re-measure, and
the branch becomes mergeable — or **a documented reason it cannot work here**, in which case bin the
fixture, keep `vsram()` and the N+1 measurement on master, and record the constraint next to the
plane A one.

Both are good outcomes. Shipping the plane A fixture is not.
