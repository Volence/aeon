# Crash reporting: fix `<unknown>` symbols, and make a shipped crash reportable

**Owner ruling (Volence, 2026-08-05):** if a player hits a crash we want them to be
able to REPORT it. A red screen says "it broke" and nothing else. The shipped build
should show something a person can photograph and send.

Two coupled pieces of work. Fixing symbols without shipping the screen helps nobody;
shipping the screen without symbols delivers half the value (raw hex addresses that
still send you to a listing). Do **Part A first** — it is the one with an unknown in
it, and Part B's value depends on its outcome.

**REQUIRED READING before starting:**
- `docs/superpowers/notes/2026-08-05-item29-mddbg-strip-ab.md` — what parcel 7 did and
  how the fault paths were verified.
- `docs/reviews/2026-07-16-emp-port-optimization-review.md`, the 2026-08-04/05 STATUS
  UPDATE sections — in particular the standing lesson that **every anchor in that
  review is stale** and claims must be re-derived against HEAD.
- `engine/system/release_fault.emp` — the current release handler and the ruled
  semantics (no stack, no `rte`, no `rts`, no `stop_z80`) and WHY.

---

## Part A — `MDDBG__GetSymbolByOffset` returns `<unknown>`

### The symptom (reproduced, not reported)

Induce a fault in the DEBUG shape and the MD Debugger screen shows raw addresses
where it should show names:

```
ILLEGAL INSTRUCTION
Offset:  006B66   <unknown>
Caller:  05E430   <unknown>
```

`006B66` is inside `Camera_Update`. It should read `Camera_Update+…`.

**Reproduce it like this** (the probe used in parcel 7 — boot does not verify the
checksum, so patching a scratch ROM is safe and needs no source change):

```bash
python3 -c "
import re
lst=open('s4.debug.lst').read()
addr=int(re.search(r'/([0-9A-F]+) :\s+Camera_Update:', lst).group(1),16)
d=bytearray(open('s4.debug.bin','rb').read())
d[addr:addr+2]=bytes.fromhex('4afc')   # ILLEGAL
open('/tmp/probe.bin','wb').write(bytes(d))
print('illegal at', hex(addr))"
```
Load `/tmp/probe.bin` in oracle, resume, screenshot.

### Facts already established — do NOT re-derive these

- The appendix **exists and is substantial**: `s4.debug.bin` is 423,388 B, the
  assembled image ends at `0x5F71E` (`DEBUG_ASSEMBLED_LEN`), and `de b2` magic sits
  at exactly `0x5F71E` with ~32 KB following.
- The Sega header **correctly spans the whole file**: `$1A4` (ROM end) reads
  `0x000675DB` = filelen−1, and `$18E` checksum is re-folded over the appended image
  (`native.rs`, `append_deb2_appendix`).
- The symbol **filter is narrow**: convsym runs `-exclude -filter "z[A-Z].+"`, which
  drops Z80 symbols only. 68k symbols are NOT being filtered out.
- convsym flags are `-input as_lst -range 0 FFFFFF -exclude -filter <F> -a`
  (`CONVSYM_FILTER`, `native.rs:2812`).
- The resolver lives at `MDDBG__GetSymbolByOffset = ErrorHandlerBlob + $64A`
  (`engine/debug/error_handler.emp`).

So: the table is present, correctly positioned, non-empty, and reachable in principle.
**The failure is in locating or parsing it, not in producing it.**

### Ranked hypotheses (test cheapest-first, and CONFIRM before fixing)

1. **The debugger cannot FIND the table.** Upstream MD Debugger locates the symbol
   data via a pointer/base it expects the toolchain to supply. The historical
   AS+convsym flow may have patched that pointer; sigil's `append_deb2_appendix`
   appends and re-folds the header but may not patch whatever locator the blob reads.
   Disassemble `ErrorHandlerBlob + $64A` and find out exactly what base it
   dereferences, then check that value in the built ROM. **This is the leading
   hypothesis and the disassembly settles it outright.**
2. **Format/version mismatch.** `deb2` is convsym's MD-Debugger-2.x format, and the
   blob is MDDBG v2.6, so this *should* match — but confirm the header fields the
   blob parses (compression flags, offset widths) against what convsym emitted. Note
   the observed header bytes are data-dependent (`04 02` here, `00 1a`/`00 06`
   elsewhere) — they encode packing, not a constant.
3. **Address-space mismatch.** The table may be keyed on addresses that do not match
   the runtime PC (e.g. an offset applied at append time, or the `-range 0 FFFFFF`
   window interacting badly with the appendix's own base).
4. **Name mangling.** `.emp` locals are demangled through the deb2 path; if entries
   exist but their names resolve to empty strings, lookup could "succeed" and print
   nothing. Weakest hypothesis — it would more likely print blanks than `<unknown>`.

### Useful cross-check

`tools/convsym` can dump a table in readable form (`-output log` is used elsewhere in
the harness, see `native::convsym_resolve`). Dump the table the build actually
appended and confirm `Camera_Update` is in it at the address the listing says. That
splits producer-side from consumer-side in one step.

### Acceptance for Part A

An induced fault in the DEBUG shape shows a real symbol name plus offset for BOTH
`Offset:` and `Caller:`. Verified in oracle by the controller, with a screenshot in
the A/B note. If the fix is toolchain-side, the strict suite must stay at its baseline
(**3024 passed / 0 failed**).

---

## Part B — the shipped build must show a reportable crash

### The ruling

Release currently shows `ReleaseFault`: mask IRQs, display off, red backdrop, freeze.
That is loud but carries **zero diagnostic content**. Volence wants a shipped crash to
be reportable.

### The decision this rests on — get it right before writing code

**The 4,272 B strip was never a space win.** The release ROM is 379,822 B of a 4 MB
cart — **9% full**. The debugger is 0.1% of the cartridge; the symbol table another
~0.7%. Space is not a constraint on the 68k side (it IS on the Z80 side — that has a
hard 8 KB with ~325 B headroom — but nothing here touches it).

So the shipped build should carry the MD Debugger **and** the symbol table. Parcels 3
and 7 are not being reverted — they converted unconditional behaviour into *flags*,
and this is choosing the other setting.

### Design

Introduce a build axis independent of `DEBUG` (grep for how `SOUND_DEBUG_HOTKEYS` and
`DEBUG` are threaded; `games/sonic4/config/game.emp` carries the
`SOUND_DEBUG_HOTKEYS` ensure, and the registry gating idiom is
`sigil/crates/sigil-harness/src/native.rs`). Three shapes:

| shape | asserts / hotkeys / selftest | MD Debugger + symbols | fault behaviour |
|---|---|---|---|
| **debug** (dev) | yes | yes | full MDDBG screen |
| **release** (what you SHIP — default) | no | **yes** | full MDDBG screen |
| **lean / gold** (opt-in) | no | no | `ReleaseFault` red screen |

Concretely: gate `engine.debug.error_handler`, the deb2 appendix, and the vectors
shape-split on `DEBUG || CRASH_REPORT` rather than `DEBUG`, with `CRASH_REPORT`
defaulting to 1. Keep `ReleaseFault` and its vector arm alive for the lean shape — it
is 46 bytes and already verified; deleting it would throw away working, tested code.

**Do NOT let this silently re-enable debug equipment.** Asserts, `SOUND_DEBUG_HOTKEYS`,
boot autoplay, `CompressionSelfTest` and the sound-debug mirror must stay `DEBUG`-only.
The whole point of item 29 was that release ships no debug *equipment*; a crash screen
is diagnostics, not equipment. If the flag algebra gets muddy, state the matrix
explicitly in `CODING_CONVENTIONS.md` §1.7 (rewritten in parcel 3 — extend it).

### Open sub-question for the implementer to ANSWER, not assume

Is the full MDDBG register/stack screen the right thing for an end user, or is a
compact "crash card" (exception name + PC + symbol, in large text) more reportable? A
photo captures either. Recommendation: **ship MDDBG** — it exists, it is verified, and
it carries strictly more information; a reporter photographing it gives us everything.
Only build a custom card if Part A proves MDDBG's symbol path unfixable.

### Acceptance for Part B

- Induced fault in the **release** shape shows the crash screen **with symbol names**.
- The lean shape still red-screens and freezes (`ReleaseFault` path intact).
- Debug shape unchanged.
- All four shapes boot and run normally; OJZ release frame pixel-identical to
  pre-parcel at the standard deterministic capture.
- No debug equipment in release: no asserts, no hotkeys, no boot autoplay, no
  selftest. Verify by symbol/byte search, not by assumption.

---

## Constraints (all binding)

- **Master is never left broken.** Branch per part, merge only when verified.
- **Emulator work is FOREGROUND ONLY** — oracle MCP deadlocks from subagents. The
  controller does all oracle verification.
- This is a **byte-changing parcel**: re-pin → `repin` → `refreeze --freeze <name>
  --ab <note>` → strict suite → `refreeze --check` + `repin --check`. Baseline is
  **3024 passed / 0 failed**.
- `repin_pins.rs` is a **hand-typed** baseline — update values *and* narrative. Do not
  auto-sync it.
- Rebuild **BOTH** sigil binaries after any sigil change:
  `cargo build --release -p sigil-cli -p sigil-harness`.
- `git add` exact paths only. Never `-A`, never stash or revert anything you did not
  change; a parallel session may be working in the sigil tree.
- **A release-shape size change past `ANCHOR_GAP` (0x400) needs the six frozen size
  tables in `sigil/crates/sigil-harness/golden/offcanonical_sizes/` hand-bootstrapped
  before the plain build will even run** — parcel 7 hit this; see its A/B note's
  "Refreeze blocker" section for the exact unblock. Re-adding ~33 KB to release WILL
  trip it in the growth direction.
- Build:
  ```
  SIGIL_BUILD=/home/volence/sonic_hacks/sigil/target/release/sigil \
  SIGIL_EMIT=/home/volence/sonic_hacks/sigil/target/release/emit_sound_blob \
  [DEBUG=1] ./build.sh [demo]
  ```
  Current master baselines: `s4.bin 730a9f99/379822`, `s4.debug.bin b3aaa1df/423388`,
  `demo.bin ea6213bc/65954`, `demo.debug.bin 18e5ec7f/93963`.

## Report

For Part A: the disassembly finding (what the resolver actually dereferences), which
hypothesis was confirmed, the fix, and the before/after screenshots.
For Part B: the flag matrix as implemented, the four shapes' crc/len, and proof no
debug equipment leaked into release.
**STOP and write it up rather than guess** on anything ambiguous — that discipline is
what made the last eight parcels land.
