---
name: Boot YM2612 Key-Off — Busy-Wait Omission and Address-Latch Race
status: SPEC — documented, DELIBERATELY NOT FIXED (owner ruling 2026-08-04)
date: 2026-08-04
scope: engine/system/boot.emp `.cold_boot` tail
supersedes: nothing (first spec for this hazard)
---

# Boot YM2612 key-off — the busy-wait omission and the dual-owner latch race

The boot sequence ends with a block that keys off all six FM channels by hand.
It has two real hardware defects. Neither is being fixed. This spec exists so
that the next person to read the block knows the defects are *known*, knows
exactly what they are, and knows why the code was left alone — rather than
discovering them fresh, "fixing" them against no hardware, and shipping timing
that only looks correct.

The review that raised this is `docs/reviews/2026-07-16-emp-port-optimization-review.md`,
section 20, finding 3. Its line anchors are stale (the tree moved `.asm` to
`.emp`); every anchor below is re-derived against the current file.

---

## 1. The code

`engine/system/boot.emp:200-230`, the last hardware step before the register
clear:

| line | what |
|---|---|
| 200-216 | the comment block (states both defects and points here) |
| 217 | `with z80_stopped {` — request the Z80 bus, spin until granted |
| 218 | `lea YM2612_A0, a6` |
| 219 | `move.b #$28, (a6)` — latch YM address = $28 (Key On/Off) |
| 220-223 | `.keyoff_part1` — three `move.b d2, 1(a6)` writes, d2 = 2,1,0 |
| 224-229 | `.keyoff_part2` — three `move.b d2, 1(a6)` writes, d2 = 6,5,4 |
| 230 | the bracket's close — release the bus |

The values are correct: {$00,$01,$02,$04,$05,$06}, skipping $03/$07 (the YM2612
channel encoding has no 3 or 7). Only the *pacing* and the *ownership* are wrong.

The two supporting anchors:

- `engine/system/boot.emp:143-148` — the Z80 `/RESET` pulse (assert, `dbf`
  delay of ~264 cycles, release). On the Mega Drive the Z80 reset line also
  drives the YM2612's `/IC` pin, so this pulse resets the FM chip. The YM2612
  requires the line held at least 192 cycles; 264 clears that.
- `engine/system/boot.emp:149` — `move.w d0, (a1)`, the bus release. **From
  this instruction onward the Z80 is executing.** In a sound build that is the
  full sound driver, not an idle loop.
- `engine/z80_bus.emp` — the `z80_stopped` context. Its acquire asserts BUSREQ
  and spins on the grant bit; it does not and cannot know what instruction the
  Z80 was in the middle of.

---

## 2. Defect A — no busy-wait between writes

The YM2612 asserts a busy flag after every data write and ignores writes that
arrive while it is set. The six data writes here are separated only by the loop
overhead:

```
    move.b  d2, 1(a6)       ; ~16 cycles
    dbf     d2, .keyoff     ; ~10 cycles
```

roughly 22-26 68000 cycles, about 3 microseconds at 7.67 MHz, against a busy
window on the order of 25 microseconds. On real silicon most of the six writes
are therefore **dropped**. The correct pacing is to poll `$A04000` bit 7 between
data writes (the same busy flag the Z80 driver's own funnel respects — see
`engine/sound/z80_sound_driver.emp:107-113`, `YM_ADDR_TO_DATA_MIN_T`, and the
machine-checked spacing `ensure`s at `:878-881`).

This defect is **mostly moot**: the `/IC` reset pulse at `:143-148` has already
keyed off every channel before this block runs. Boot silence is guaranteed by
the reset, not by these writes. The block is belt-and-braces, and a
belt-and-braces block whose writes get dropped is still belt-and-braces.

The existing comment at `:200-205` already said this before this parcel, and it is accurate; `:206-216` were added to cover defect B and point at this spec.

---

## 3. Defect B — the dual-owner address-latch race (the sharper one)

This is the part the code comment does *not* cover, and it only exists in
**sound builds**.

The YM2612 is a two-port device: write a register number to the address port
($A04000 / $A04002), then the value to the data port ($A04001 / $A04003). The
address is a **latch**. It persists until someone writes a new one. There is one
latch and, in a sound build, two masters that write it.

By line 217 the Z80 sound driver has been running for the entire RAM clear
(released at `:149`, ~360k cycles earlier). It writes the YM continuously —
sequencer output, DAC parking, Timer-A programming. Every one of those writes is
an address/data *pair* with a small gap between the halves, and the driver's
`ensure(cycles(...) >= YM_ADDR_TO_DATA_MIN_T)` guards prove that gap exists.

the bus request at `:217` can land in exactly that gap:

```
  Z80:  write $4000 <- reg N        (address latched = N)
        ... BUSREQ granted here, Z80 halted mid-pair ...
  68k:  write $A04000 <- $28        (address latch clobbered: now $28)
  68k:  write $A04001 <- $00..$06   (six key-off writes)
  68k:  BUSREQ released
  Z80:  write $4001 <- value        (resumes — lands on register $28)
```

The Z80's data byte, intended for register N, is written to **register $28, Key
On/Off**. Depending on the byte that is a spurious key-on or key-off on an
arbitrary channel — the one class of glitch this block was added to prevent.

The symmetric failure also exists: the 68k's own `$28` latch is safe only
because it holds the bus for the whole block, but the *driver's* next write
after resume assumes a latch value that no longer holds.

Nothing in the build catches this. The driver's spacing `ensure`s prove the Z80
half is well-formed; they say nothing about a second master reaching in between.

---

## 4. Why it does not bite today

1. The `/IC` reset at `:143-148` has already silenced the chip, so the block is
   redundant on the path it was written for.
2. The race requires the bus request to land inside a window of a handful of Z80
   T-states, once, during a single boot.
3. If it does fire, the damage is one stray write to $28 during the boot frame,
   before any music has been started — audibly nothing.

It is a latent correctness defect, not an observed bug. It has never been seen,
and on an emulator it never will be: the emulators available here do not model
the YM2612 busy flag or the address-latch contention at this granularity.

---

## 5. The two candidate fixes (neither applied)

**Candidate 1 — key off before the bus release.** Move the block to sit between
the `/IC` reset release (`:148`) and the bus release (`:149`). There the 68k
already owns the Z80 bus, the Z80 has not executed a single instruction, and
there is exactly one master touching the YM. The bus request / release are
then unnecessary and defect B disappears entirely. Defect A remains and would
still want a busy poll.

**Candidate 2 — drop the block in sound builds.** Under `SOUND_DRIVER_ENABLED`,
the `/IC` pulse silences the chip and the driver's own init takes ownership
immediately afterwards. The block adds nothing a sound build needs, and removing
it removes both defects along with the second master. The no-sound shapes would
keep it (there, the Z80 is the idle program and never touches the YM, so there is
no second master and defect B cannot occur).

Candidate 2 is the smaller change and the more honest one. Candidate 1 is the
more conservative.

---

## 6. Why it is deliberately NOT fixed

Owner ruling, 2026-08-04, verbatim:

> "LEAVE THE YM KEY-OFF BUSY-WAIT RACE UNTOUCHED, documented with a written
> spec — there is no real hardware here, and getting its timing wrong is worse
> than the current state because it would look addressed."

The reasoning, expanded:

- **The defects are hardware-only.** Both require silicon behaviour (the busy
  flag, the latch) that no emulator in this workspace models. There is no real
  Mega Drive available for verification — see the standing project constraint
  that all verification is emulator-based.
- **A fix cannot be validated.** Adding a busy poll means choosing a poll
  protocol and a timeout against a chip we cannot measure. Moving the block
  means asserting that the new position is safe with respect to the `/IC` pulse
  and the driver's start, again unmeasurable here.
- **A wrong fix is worse than the documented status quo.** The current state is
  a redundant block with a known, harmless-in-practice flaw. A plausible-looking
  but mis-timed busy poll would read as "this was handled", and the next person
  would stop looking. An unverifiable fix converts a documented known into an
  undocumented unknown.

So the code is byte-for-byte unchanged and this document is the deliverable.

---

## 7. When to revisit

Revisit if **any** of these becomes true:

- Real Mega Drive hardware becomes available for verification.
- The emulator (`oracle`) gains a YM2612 busy-flag / address-latch model
  accurate enough to observe a dropped write or a clobbered latch.
- The block stops being redundant — i.e. someone removes or shortens the `/IC`
  reset pulse at `:143-148`, at which point boot silence starts depending on
  these six writes actually landing. **This is the dangerous one.** If you are
  touching the reset pulse, read this section first.
- Sound builds start doing anything on the Z80 between `:149` and `:217` that
  matters more than a boot-frame glitch.

Do not apply either candidate fix without an owner ruling.
