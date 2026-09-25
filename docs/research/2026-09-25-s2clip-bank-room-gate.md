# S2CLIP-BANK-ROOM-GATE: the bank-room gate fired at the wrong threshold (2026-09-25)

Branch `parcel/s2clip-room-gate`. Files changed: `tools/bganim_room.py`, `tools/test_bg_emit.py`,
this report, `docs/DEFERRED_WORK.md`. No `.emp`, no map, no clip manifest or bake tool touched.

## Reproduction (base `531d9953`, unmodified)

`DEBUG=1 S2CLIP=s2_ehz_boot ./build.sh` exited **1**. The emitter is `tools/bganim_room.py --gate`
(build.sh's post-sigil lane, "BG-animation section room"). Its text:

```
bganim_room [s4.s2clip.debug.lst]:
  Art_Sonic 0x80D0E + 101536 = 0x999AE; anchor 0xA8000
  terminus: CHECKED by both instruments — ... all 58962 B of that region are zero in s4.s2clip.debug.bin
bganim_room: FAIL — the bank placement rule is broken in this shape.
  `dac_banks` is declared at 0xA8000 but packed data ends at 0x999AE, leaving 58962 B < DATA_GROWTH_RESERVE 49152 B.
  The rule ...: dac_banks = align_up(packed_end + reserve + grace, 0x8000) = 0xB0000, sound_bank = ... = 0xC0000.
```

(The ROM itself was written: `s4.s2clip.debug.bin`, crc32 `19e78bdb`, 848,295 B.)

## Diagnosis

**(a) Was the measurement right? Yes.** 58,962 B is the real room in this shape:
`dac_banks` 0xA8000 (the map's anchor, shared by every sound-on shape) minus the packed-data end
0x999AE (`Art_Sonic`'s LMA 0x80D0E from the clip listing + the 101,536 B blob). The terminus is
checked against both the listing and the ROM image, and the extent is byte-compared. The clip act's
level data is larger than the shipped act's (shipped debug end 0x93302), which is why this shape is
closer to the anchor. Nothing here read the shipped act's numbers.

**(b) Was the threshold right? No, and that also makes the message look wrong.** The ruled rule
(games/sonic4/map.toml "WHY THE RULE GREW A SECOND TERM", and commit 446a27d9's own message) says
the gate fires at `room < DATA_GROWTH_RESERVE`, and GRACE sits "INSIDE the align_up and OUTSIDE the
gate's threshold". GRACE sets where a RE-LAYOUT puts the anchor. It does not set when the gate
fires. But the fail arm compared `anchor < rule_anchor(packed_end)`, and since 446a27d9 that value
includes GRACE. So the arm actually fired at `room < RESERVE + GRACE`, rounded to a 0x8000 window,
which means fired whenever `packed_end > 0x94000` for the 0xA8000 anchor. The message kept the
08-26 wording from when the two conditions were the same. So "58962 B < 49152 B" was a
correct description of a rule the arm was not testing.

The numbers in that message:
- **58,962 B** = the room under `dac_banks` = 0xA8000 − 0x999AE.
- **49,152 B** = `DATA_GROWTH_RESERVE` (0xC000), the floor the ruling says must stay free.
- The condition that really fired: 0xA8000 < align_up(0x999AE + 0xC000 + 0x8000, 0x8000) = 0xB0000.

**Is the clip ROM out of room? No.** It has 58,962 B under the anchor, which is **9,810 B above the
reserve**. It has used 22,958 B of the 32,768 B grace, and the reserve is untouched.

**The canonical shapes had the same defect, but it was hidden.** At base, `s4.debug` (packed end
0x93302) printed "growth before this gate fires again: 36094 B". The arm as written would have
fired after **3,326 B** (at 0x94000). That line has overstated every shape's margin by up to one
grace window since 09-04.

## Fix

- The arm compares the room with the reserve: `room < DATA_GROWTH_RESERVE`. Because the message
  describes the condition that was tested, it is now true by construction: `room under `dac_banks`
  = 0xA8000 - 0x<end> = N B, which is LESS than DATA_GROWTH_RESERVE 49152 B (short by K B)`, and
  it names what each address is. The remedy still names the rule's re-layout anchor pair
  (reserve + grace).
- A new report-only band covers the case where the anchor is below this shape's rule value but the
  reserve still holds. It says how much of the grace is spent, and that the grace is NOT guaranteed
  there. Before this, the "guaranteed >= grace" sentence would have been printed with a negative
  slack.
- **Effect on every shape, not only the clip:** the gate now fires `GRACE` bytes (window-rounded)
  later than the code did before, which is the threshold the ruling set. This does not loosen the
  ruled gate. It restores the ruled gate from a stricter accidental one. If the owner wants the
  stricter behaviour, that is a new ruling (raise RESERVE), not this arm.

## Proof

- **The new test** is `TestBgAnimRoomOverCommittedFixture::test_the_gate_threshold_is_the_reserve_and_grace_is_outside_it`.
  It covers three rooms derived from the fixture's packed end and the constants: R (passes), R−2
  (fails, with exact message text) and R+G/2 (passes). In all three the anchor is below
  `rule_anchor`.
  - **Red-first against the unfixed tool:** 4 failed / 1 passed on the selected pair. The R and
    R+G/2 rows gave rc 1 != 0, and the R−2 row failed on the message.
  - **Mutation after the fix:** the arm was reverted on disk to `if anchor < want:` (diff shown in
    the session) and the fixture class went **2 failed / 36 passed** (subtests R and R+G/2). The
    file was then restored with `git checkout` from the fix commit.
- `tools/test_bg_emit.py` with the fix: **120 passed, 29 subtests passed** (rc 0).
- `DEBUG=1 S2CLIP=s2_ehz_boot ./build.sh`: **rc 0**. The ROM is unchanged, crc `19e78bdb`, 848,295
  B. The tool changes, the bytes do not. The gate block now reads "declared 0xA8000, 0x8000 BELOW
  this shape's rule value — 22958 B of the 32768 B grace is spent, the reserve is intact; growth
  before this gate fires again: 9810 B".
- The canonical ROM CRCs before and after are in the DEFERRED_WORK entry and the parcel's final
  report. The same sigil binary was used for both (sha256 `e79152d8…b708c`).

## Open

- **The two-zone clip (Chemical Plant, `parcel/s2-two-zone-act`) has 9,810 B before this gate fires,
  and this time the firing would be real.** If that act's data grows the packed end past 0x9C000,
  the remedy is the rule's: move both anchors (and hand them to sigil), or rule the clip shape out
  of the shared anchor. Loosening is not a remedy.
- `dplc_straddle` prints a MARGIN WARNING on the clip debug shape (nearest forbidden art-base shift
  3,343 B). It is not a gate, it is pre-existing, and it also prints on the canonical shapes. It is
  noted here only because the clip act's growth moves `Art_Sonic`.
- The booking row in `docs/lane-status.json` is left to the overseer.
