# Lab chord list — on-screen verification

Build `26750443` / `e05ad69f`, `s4.debug.bin` 845594 bytes, 3037 symbols, my own
Oracle instance (not the owner's window — see the last section).

The implementing agent could not drive an emulator, so every claim in its report
about what appears on screen was inference from code. This is the measurement.

## Confirmed as the agent predicted

| Step | Expected | Measured |
|---|---|---|
| Hold START, no direction | 4 rows arm | `DFLT` / blank / `PTCH` / `ACT` |
| START + RIGHT | `UWTR` | `UWTR`, background changed to the underwater parallax |
| START + LEFT x2 | `DFLT`, then wrap to `GRND` | wrapped to `GRND`; perspective floor on screen |
| preset row on a preset entry | `8` + verdict glyph | `8` + arrow, appeared exactly on the preset row |
| preset row elsewhere | blank | blank on `DFLT` and `UWTR` |
| START + UP | nothing | list unchanged (`GRND`/`8`/`NONE`/`ACT`) |
| START + DOWN | nothing | list unchanged |

`PTCH` at boot is worth naming: the agent flagged that one specifically as
inference from section 0's binding rather than an observation. It is now
measured.

START+UP and START+DOWN move the player, because UP/DOWN are debug free-flight
movement. They do not touch the list. That is the distinction the owner needs:
the chord is inert, the buttons are not.

## REFUTED — the agent's report is wrong on one row

Its drive script says "START + UP, START + DOWN, START + A — all three should
now do **nothing**".

**START + A is NOT inert. It cycles the character.** Measured on
`Player_Chardef` ($FFEA2E):

    before START+A   $00012044
    after  START+A   $0001207A     <- changed
    after  A alone   $000120B0     <- changed again

This follows from the agent's own rider rather than contradicting it: it deleted
`Debug_CharacterHotkey`'s START veto, which is what made A unconditional. Both
halves of its report are individually true and the conclusion drawn from them is
not — "the veto is gone" and "START+A does nothing" cannot both hold, because
removing the veto is exactly what makes the chord fire.

Not judged a defect here: A alone cycling characters is the pre-chord behaviour
being restored, and nothing in the list is reachable by START+A any more. It is a
SURPRISE, not a fault — the owner will press START+A out of habit and swap
character instead of getting nothing.

## The owner's window

`pgrep -x oracle_gui` finds no process: his window is not open, so there was
nothing to reload and none was launched. Auto-launch is approved but putting an
unrequested window on his screen at 02:20 local is not, so this is left for him.
