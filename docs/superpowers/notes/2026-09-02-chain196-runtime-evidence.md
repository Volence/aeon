# Chain 196 (alignment flip) — the runtime evidence, and the falsifier that outgrew it

The aeon lane's foreground verification of the two items sigil TAGGED for the controller
in packet s12 §12.9, plus the whole-ROM falsifier §12.2 asked for and the build control
phase 1 never reached. No agent did any of this: subagents cannot drive the emulator
(they deadlock), so every measurement below is the controller's own.

Subject: `parcel/alignment-flip-hole-196` @ `8c0983b5` built with sigil `443d1544`
(`land/alignment-flip-196` = sigil master `9a2f40c6` + parcel `23ee52f0`).
ROMs: s4 `ac10ab85`/719325, s4_debug `fa866f19`/736345, demo `30a31d81`/96458,
demo_debug `51056291`/101323 — equal to §12.1's post column on all four.

## 1. The two TAGGED items

**Sound_PlaySFX, plain sound-on `s4.bin`.** `Sound_PlaySFX` is at `0x7FBC` in the
post-flip listing, below the `0x8000` ceiling `SoundTablesZ80_Head` still occupies.
Live pad input does not drive the player from a cold boot in this shape, so the driver
was the standing replay fixture, armed the documented way — `Input_Source` =
`INPUT_PLAYBACK` (1), `Replay_Ptr` = fixture + `REPLAY_HEADER_LEN` (20), both fields
read back before resuming:

| fixture | entry | result |
|---|---|---|
| `Replay_OJZ_Fixture` (`0xA4972`) | `0xA4986` | `Replay_Done` = `$FF`, `Input_Source` back to LIVE, no fault |
| `Replay_OJZ_Slide_Fixture` (`0xA4A82`) | `0xA4A96` | `Replay_Done` = `$FF`, `Input_Source` back to LIVE, no fault |

`Sound_PlaySFX` was reached **5 times** during the first fixture. One hit was caught at
the breakpoint and attributed rather than counted: return address `0x00010AC6`, and the
four bytes at `0x00010AC2` are **`4EB8 7FBC`** — `jsr ($7FBC).w`, inside `Player_Jump`
(`Player_Jump.no_carry`), with `d0` = `0x62`. That is one of the eleven re-encoded sites,
executing, resolving to the right address. The *count* alone would not have shown which
site; the return address is what makes it a site and not a coincidence.

**Raster_Install, `s4.debug.bin`.** `Raster_Install` is at `0x7FDC`. Its two callers are
`Debug_BandDemoHotkey`'s tail calls, and the hotkey's own Gate 1 is
`tst.b Input_Source / bne .done` — it is live-input-only **by design**, precisely so a
fixture holding START cannot install a program mid-playback. So this one cannot be driven
by replay, and was driven by the live chord the source names: START held, UP pressed
(edge) installs a program; START held, DOWN pressed installs `Raster_Program_None`.
`Raster_Install` was hit once per branch, **2 hits**, no fault.

## 2. The falsifier, widened as sigil asked

§12.2 records that a Sound_PlaySFX-only probe cannot see the debug shape's crossing, and
that the general form is "every head label that crosses". The general check is cheaper
than the specific one and does not need a label list at all: **scan for the encodings.**

Counts are byte-scans of the shipped ROMs, not listing reads:

| ROM | `jsr ($7FBC).w` | `jmp ($7FBC).w` | `abs.l` survivors to that target |
|---|---|---|---|
| `s4.bin` | 9 (`0x10340 0x106AA 0x10724 0x10AC2 0x10E86 0x10EE2 0x11200 0x1128C 0x115C4`) | 2 (`0x11018 0x11636`) | **0** |

9 + 2 = **11**, which is §12.2's count, arrived at independently. `s4.debug.bin` carries
2 `jmp ($7FDC).w` at `0xA6870` and `0xA6880` — both inside `Debug_BandDemoHotkey`
(`0xA67C8` + `0xA8` / `+0xB8`) — and 0 `abs.l` survivors. **No half-converted state in
either shape**, which is the property a per-site count cannot express.

**The hazard the flip actually risks** is not "a site was re-encoded" but "a site was
re-encoded whose target does not survive sign extension": `abs.w` sign-extends, so any
target ≥ `0x8000` addresses RAM instead of ROM. Scanning all four shapes for every
`4EB8`/`4EF8` encoding whose operand is ≥ `0x8000`:

| ROM | abs.w jsr/jmp encodings | targets ≥ `0x8000` |
|---|---|---|
| `s4.bin` | 109 | 1 — `jmp ($FFFE).w` @ `0xA4F3E` |
| `s4.debug.bin` | 158 | 2 — `jmp ($FFFE).w` @ `0xA71F0`; `jsr ($9542).w` @ `0xA970A` |
| `demo.bin` | 10 | 1 — `jmp ($FFFE).w` @ `0x104D6` |
| `demo.debug.bin` | 10 | 1 — same |

All four resolve outside this parcel's subject, and each was resolved rather than waved
past. `0xA970A` is `EndOfRom + 0x17D6` — inside the deb2 symbol appendix, which is data.
The `$FFFE` ones are `ErrorHandlerBlob + 0x212` in **both** sonic4 shapes — the same
displacement into the vendored MD Debugger blob, i.e. blob content, byte pairs in a
pre-assembled island this parcel does not touch. The control that settles it: the same
pattern is present in a **pre-flip** `s4.debug.bin` at `0xA71FC`, twelve bytes off the
post-flip `0xA71F0` — exactly the shift the flip causes to everything after it. It is
pre-existing; the flip moved it, it did not create it.

So: **zero abs.w encodings in engine or game code, in any shape, whose target would sign
extend into RAM.**

## 3. The build control phase 1 never reached

The question a matching CRC cannot answer on its own: did the *aeon-side* edits (the two
`map.toml` hole rows, the two fixture re-stamps) move the bytes, or did sigil's flip?

Same tree, same source, pre-flip binary (`sigil 0.1.0 (8951389a)`):

```
s4.bin  fdd1cf81  719387
```

That is the **chain-195 golden verbatim** (§12.1's `pre` column), not the post-flip
`ac10ab85`/719325. The aeon-side edits move nothing on their own; the whole −62 B is the
flip's. Two things worth recording beside it: the pre-flip binary did **not** refuse the
`at = 0x3F0` hole row — it built the old layout without complaint, so that row is not
self-checking against the wrong toolchain — and the control landing exactly on a golden
nobody re-derived for it is an independent check of the 195 baseline itself.

The pre-flip control was taken through `FAST=1`, whose banner is right that it verifies
nothing; it is the correct instrument here because the question is *which bytes does this
binary emit*, which is the one thing FAST does not skip.
