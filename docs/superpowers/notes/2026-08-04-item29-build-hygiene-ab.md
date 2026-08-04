# Item 29 (build hygiene) — A/B evidence

Evidence packet for the `item29-build-hygiene` provenance chain entry, per
`sigil/crates/sigil-harness/golden/ab/AB_PROTOCOL.md`. Class: **PS** (pure-size),
with the strongest identity claim available: **the bytes the console executes
are unchanged in every shape.** What changed is what sits *past* them in the
release file, plus a comptime assertion and documentation.

## Builds compared

| shape | OLD (`master` @ `faa3687`) | NEW (`parcel/item29-build-hygiene` @ `e4b7fd4`) | delta |
|---|---|---|---|
| `s4.bin` (release) | `crc=56f1b3ba` / 413,246 | `crc=b06fc575` / **384,048** | **-29,198 B (-7.1%)** |
| `s4.debug.bin` | `crc=abf1d304` / 423,383 | `crc=abf1d304` / 423,383 | **0 — byte-identical** |
| `demo.debug.bin` | `crc=d4c00097` / 93,929 | `crc=d4c00097` / 93,929 | **0 — byte-identical** |

The two DEBUG shapes reproduce their previous CRCs exactly, which is the
control: the gate is shape-selective and touches nothing else.

## Result 1 — the release file is exactly the assembled image

```
plain len                384048 = 0x5DC30 = pins::ASSEMBLED_LEN = EndOfRom
bytes past EndOfRom      none (file ends there)
ROM-end pointer $1A4     0x0005DC2F  (= len - 1, correct)
header checksum $18E     8a d9       (unmodified — emit_rom already folded it
                                      over exactly these bytes, so no re-fix)
```

The assembled prefix `[0, EndOfRom)` is byte-for-byte what it was before, so
every gameplay address, every pin and the whole cartridge image are untouched.
`repin --check` reports **pins.rs unchanged**, which is the independent
confirmation.

Debug still carries its appendix: `de b2 04 02 …` at `0x5F722`, 32,437 trailing
bytes.

**Detection note worth recording.** A first pass concluded this leak was already
closed, because it grepped the release ROM for the ASCII string `deb2` and got
zero hits. The appendix magic is the **binary word `$DE $B2`**. The ASCII grep is
a false negative and nearly let a 7.1% release leak through a second time — the
review's own anchor (`build.sh:130-134`, convsym) was separately stale, since
build.sh no longer calls convsym at all. Two independent stale signals pointing
the same wrong way.

## Result 2 — the new release gate is non-vacuous

`native_rom_plain` now uses `assert_rom_matches_release`: exact identity against
the reference with an **empty allowlist** (the convsym/fixheader post-steps do
not run in this shape, so `$18E`/`$1A4` must MATCH rather than differ) plus a
length pin equal to `EndOfRom`.

Proved live: appending 4 KB of fake `DE B2` data to `s4.bin` **fails** the gate
with the named message (`left: 388144, right: 384048`); the file was restored and
the gate re-passed. This bar is strictly stronger for the plain shape than the
convsym bar it replaces. `assert_rom_matches_convsym` remains the DEBUG bar.

## Result 3 — the release ROM boots and runs

`s4.bin` (release shape, no symbols, changed file length and ROM-end pointer)
loaded from reset and driven 240 frames of right-scroll: OJZ renders correctly
with parallax, terrain and ring row intact, and the 68k is in normal code
(`EntityWindow_InitSection`), not the error handler. This is the check that
matters most here — the header fields moved, so "it still boots" is not free.

## Result 4 — the hotkey ensure is real

`ensure(SOUND_DEBUG_HOTKEYS == 0 || DEBUG == 1, "SOUND_DEBUG_HOTKEYS requires DEBUG=1")`

Verified by inverting it and confirming a hard build error with that message,
then restoring. Byte-neutral in every sanctioned shape (Config-A already sets
`debug: true`), which the unchanged debug CRCs above confirm.

## Gates

Strict suite **3000 passed / 0 failed** — the baseline exactly, including
`native_rom_plain`, `native_rom_debug`, `deb2_appendix_negative_controls`,
`config_b_full_file`, `demo_plain_full_file` and `provenance_chain_holds`.
`repin --check` clean.

## Not covered here

- **Part 4 of item 29 (the error-handler / MDDBG strip) is NOT in this parcel.**
  It is blocked on an owner ruling and written up in `docs/DEFERRED_WORK.md`.
  4,272 bytes still ship in both shapes, `demo` included.
- The `RaiseError`/`Console` half of the review's item turned out to be a
  **non-leak**: both are AS macros with zero call sites, and `__DEBUG__` is only
  defined in debug builds, so they are inert definitions in a residual that emits
  no bytes in release. Gating them would be cosmetic. Recorded rather than done.
- The harness's full-file model helpers (`build_native_full_file`,
  `build_full_file_chained`) still append in the plain shape by design — they
  test the appendix *mechanism*, not a shipped artifact, and two t24 negative
  controls depend on that. Making them shape-aware is a clean follow-up that
  would require a golden re-freeze.
