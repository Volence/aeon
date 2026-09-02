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
target ≥ `0x8000` addresses RAM instead of ROM.

The first version of this scan covered the **whole ROM image** while the claim it was
supporting was about **engine and game code**, and it is written up here in its corrected
form because sigil's review (sigil `be676684`) caught two things in it that the original
prose got wrong. Both are recorded in §4.

The population the claim is about is the emitted engine+game region, `[0x200,
ErrorHandlerBlob)`: below it is our code and data, `ErrorHandlerBlob`..`EndOfRom` is the
vendored MD Debugger island (a pre-assembled blob, `0xF56` bytes in **both** shapes pre
and post — itself evidence its content is untouched), and past `EndOfRom` is the deb2
symbol appendix. Word-aligned scan, chain-195 goldens (`fdd1cf81`/719387,
`0f6b1359`/736391) as the pre side:

| shape | code region `[0x200, blob)` | blob + appendix | whole image |
|---|---|---|---|
| `s4.bin` pre | 97 enc, **0 flagged** | 2 enc, 1 flagged | 99, 1 |
| `s4.bin` post | 108 enc, **0 flagged** | 1 enc, 1 flagged | 109, 1 |
| `s4.debug.bin` pre | 154 enc, **0 flagged** | 1 enc, 1 flagged | 155, 1 |
| `s4.debug.bin` post | 156 enc, **0 flagged** | 2 enc, 2 flagged | 158, 2 |

Two things fall out, and the bounded population is what makes both legible:

**The conversion reconciles exactly.** Code-region `abs.w` encodings go 97 → 108 in `s4`
(**+11**) and 154 → 156 in `s4_debug` (**+2**) — the converted sites and nothing else. The
whole-image counts are off by one in *opposite* directions (109 vs a predicted 110; 158 vs
157), and that discrepancy is not in the code at all: it is the blob+appendix band moving
2 → 1 in `s4` and 1 → 2 in `s4_debug` as a 62-byte shrink re-aligns data past the code.

**Zero flagged operands in the code region, pre and post, in both shapes.** That is the
statement the claim needs: not "the flags I found resolve outside the subject" but *the
subject contains none* — and it holds on the pre side too, so it is a property of the
region, not a lucky post-flip reading.

The flagged encodings all sit outside that region and are data being read as code:
`0xA970A` is `EndOfRom + 0x17D6`, inside the deb2 appendix; the `$FFFE` ones are
`ErrorHandlerBlob + 0x212` in both sonic4 shapes, the same displacement into the vendored
blob.

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

## 4. What the first version of §2 claimed and got wrong

Sigil re-derived this evidence from the other side of the flip (`be676684`) and corrected
two things. Both are recorded here rather than quietly fixed, because the corrected
sentences are the ones a future session will rely on without re-deriving them.

**"Pre-existing; the flip moved it, it did not create it" was true of one flag and was
written as though it covered both.** It is right about the `$FFFE` pattern: pre-flip
`s4.debug.bin` carries it at `0xA71FC`, twelve bytes off the post-flip `0xA71F0`, which is
exactly the shift the flip causes. It is **wrong about `0xA970A`**, which has *no*
pre-flip counterpart — pre-flip `s4.debug.bin` contains no `4EB8`/`4EF8` anywhere in
`0xA9600..0xA9900` at any operand. That flag is **new**, created by the shrink re-aligning
the deb2 appendix: the surrounding bytes are an ascending 16-bit table in pairs
(`9218 4E6A 92BE 4E78 9346 4E86 …`) that passes straight through the `4EB8`/`4EF8` range,
and post-flip one pair lands reading as `jsr ($9542).w`. Still data, still harmless — but
"the flip did not create it" is false of it, and that sentence was the falsifier's whole
claim about what the flip did.

**The prose counted five flags and then resolved "all four."** 1 + 2 + 1 + 1 = five; the
unaccounted one was `0xA970A`, the same flag the sentence above was wrong about. Two
errors, one cause: the appendix flag was never really looked at.

Neither bears on whether the flip is sound. Both bear on what the evidence *proves*, which
is why §2 was rewritten around a bounded population instead of patched in place. The
lesson worth keeping: a whole-image scan defending a claim about code will always carry
flags that need individual excuses, and each excuse is a place to be wrong. Bounding the
scan to the claim's own population removed the excuses entirely and turned the result from
"the flags resolve outside the subject" into "the subject contains none."
