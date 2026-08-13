# Replay Net Re-Stamp (Effects P3, Parcel 0) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement
> this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **THIS PLAN CANNOT BE RUN BY SUBAGENTS.** Tasks 2-7 drive the oracle emulator over MCP,
> and oracle MCP calls from a background agent deadlock the socket. The controlling session
> must execute those tasks itself, foreground. Tasks 1, 8, 9 are safe to delegate.

**Goal:** Return master's replay net to green by RE-STAMPING the stale checkpoint hashes in
`ojz_fixture.bin` (and `ojz_slide_fixture.bin` if it is also red), preserving the input
stream byte-for-byte, so that Effects P3 parcels C and D have a trustworthy regression net.

**Architecture:** Iterate against a patched ROM image rather than re-recording. Each cycle:
run playback, take the `REPLAY DESYNC` trap, read the actual hash from `d0` and the tick from
`d1`, patch that checkpoint's 4-byte payload directly in a working copy of `s4.debug.bin`,
`reload_rom`, repeat. When playback reaches the end, apply the accumulated hashes to the
fixture file on disk and rebuild once. The input stream is never touched, so the fixture's
proven coverage is inherited rather than re-established.

**Tech Stack:** aeon `.emp` engine + `./build.sh`; `tools/replay_pack.py` (existing, has
`--selftest`); oracle emulator via MCP; Python 3 for byte patching.

---

## Context an implementer needs before starting

**This is pre-existing debt, not Phase 3 work.** Master's net is red, inherited from the
Knuckles C4 merge (`50d54612`) whose re-stamp was never done. Spec:
`docs/superpowers/specs/2026-08-13-effects-p3-design.md` §2.0.

**Five facts that were verified this session and contradict the docs. Trust this list, not
the notes:**

1. **The "probe-ROM logger runbook" does not exist.** Four documents (including this parcel's
   own spec) say to re-stamp "via the probe-ROM logger per
   `docs/superpowers/notes/2026-08-09-replay-net-rerecord-ab.md`". That note contains no such
   thing — `grep -n probe` on it exits 1. The technique is described in
   `docs/superpowers/notes/2026-08-05-sst-fold-ab.md:27-38`, and was **never committed as
   code**: it was 16 bytes of hand-assembled 68k written over ROM bytes, and neither the bytes
   nor the patch offsets were recorded. **Do not plan around it.** Task 8 fixes the citations.
2. **Re-recording is impossible; only re-stamping works.** The fixture's input stream uses
   `BUTTON_C` in four runs — including `0x22` (DOWN+C) at ticks 1237 and 1248, which is the
   spindash rev *inside the desyncing region*. The oracle driver cannot press `c` at all
   (three attempts, no effect, per `notes/2026-08-13-replay-rerecord-attempt.md:38`).
   Substituting A/B would change the stream and forfeit the fixture's coverage.
3. **All statistics in the 2026-08-09 note are stale.** It claims 1,670 ticks / 272 B and
   1,942 ticks / 288 B; the bytes on disk are **1721 ticks / 27 checkpoints / 272 B** and
   **2350 ticks / 37 checkpoints / 336 B**. The fixtures were replaced twice after that note
   (`f3537d44`, `5129060c`). Its CRCs and byte counts are rotted too. The packer's `dump` is
   truth.
4. **There is no automated runner.** The replay net is not a pytest, not a cargo test, not in
   `test.sh`, and not in CI. The aeon suite's "941 passed, 2 skipped" skips are
   `test_s4lint.py` looking for a `main.asm` that no longer exists — **not** the replay net.
   The net fails only when a human runs the oracle procedure, which is why master has been red
   without anything saying so. Task 9 records that gap.
5. **A pure re-stamp needs no sigil ritual.** Only the 4-byte hash payloads change, so the
   fixture's byte length is identical, `EndOfRom` does not move, and
   `pins.rs:44 DEBUG_ASSEMBLED_LEN` is undisturbed. **No repin, no refreeze, aeon-only.**
   (A true re-record would change the length and drag in the full ritual — another reason not
   to.)

**The failure, verified from the fixture bytes:**

| | value |
|---|---|
| trap tick (`d1`) | `0x00000502` = 1282 |
| actual (`d0`) | `BBB93779` (note-reported; re-measure in Task 2) |
| expected (`d2`) | `1F420103` — **confirmed** as the ring-1280 checkpoint payload |
| cause | spindash charge: ring 1212 holds `0x02` (DOWN) x25, then `0x22` (DOWN+C) |

Ring index + 2 = `Logic_Tick` (the recorder's first logged tick was 2). Checkpoints at ring
0, 64, 128, … 1664. Everything at or below ring 1216 passes; **everything above 1280 is
UNMEASURED** because the trap stops the run. Do not assume "7 stale" — iterate until done.

**The hash is layout-proof by contract** (`engine/system/replay.emp:7-16`, `:49-64`, pinned by
six `ensure`s at `:87-92`). Corollary: a layout break desyncs at checkpoint **0**. A run that
gets 1280 ticks in and *then* diverges is behavioural — which is what makes this a legitimate
re-stamp rather than a bug to fix.

**Symbols are build-specific. Re-derive them every time from `s4.debug.lst`** — a prior
handoff still quotes a `Replay_Ptr` from two layouts ago. Values for the current build:

| symbol | addr |
|---|---|
| `GameState_OJZScroll_Init` | `$A1734` |
| `Replay_OJZ_Fixture` | `$A1DA0` |
| `Replay_OJZ_Slide_Fixture` | `$A1EB0` |
| `Logic_Tick` | `$FF8004` |
| `Ctrl_1_Held` | `$FF802C` |
| `Input_Source` | `$FF803A` |
| `Replay_Done` | `$FF803C` |
| `Replay_Ptr` | `$FF8040` |

**Oracle hazards, all previously measured:**
- **Never watchpoint `Replay_Done`** — a watchpoint on `$FF803C` wedges the emulator. Poll it.
- Breakpoint stops land a few instructions **early**; never trust the stop PC.
- A desync trap **looks like a hang** over MCP (`status.running=true`, `Logic_Tick` frozen).
  Check `status.symbol_at_pc` for `ErrorHandlerBlob` before concluding anything is broken.
- One oracle instance only. At time of writing PID 1297412 is running the **wrong ROM**
  (an effects-p2 worktree build).
- The DEBUG OJZ scene boots with debug-fly ACTIVE and swallows ~2,700 frames (~12 s) before
  logic ticks flow. This is why the fixture opens with a `0x10` (B) tap at tick 1024.

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `games/sonic4/data/replays/ojz_fixture.bin` | The standing fixture (272 B, 1721 ticks, 27 cps) | Modify — hash payloads only |
| `games/sonic4/data/replays/ojz_slide_fixture.bin` | The slide-crossing fixture (336 B, 2350 ticks, 37 cps) | Modify only if Task 6 finds it red |
| `/tmp/.../scratchpad/restamp/` | Working ROM copies, harvested hashes, patch log | Create (never committed) |
| `docs/superpowers/notes/2026-08-13-replay-net-restamp-ab.md` | Evidence record for this parcel | Create |
| `docs/superpowers/specs/2026-08-13-effects-p3-design.md` | §2.0's false probe-ROM citation | Modify |
| `docs/superpowers/notes/2026-08-09-replay-net-rerecord-ab.md` | Stale stats/CRCs; false-citation source | Modify — add a superseded banner |
| `docs/DEFERRED_WORK.md` | The "no automated runner" gap | Modify — new entry |
| `tools/test_replay_fixture.py` | Structural integrity of both fixtures | Create |

---

## Task 1: Establish a clean, verified starting point

**Files:**
- Create: scratchpad dir
- Read: `s4.debug.lst`

- [ ] **Step 1: Confirm the tree is clean of anything that would confuse a byte comparison**

```bash
cd /home/volence/sonic_hacks/aeon
git status --short games/sonic4/data/replays/ engine/ docs/
git log --oneline -1
```

Expected: no modifications under `games/sonic4/data/replays/` or `engine/`. (Modified files
under `games/sonic4/data/editor/` are another session's work under the auto-commit daemon and
are expected — leave them alone, and never `git add -A`.)

- [ ] **Step 2: Reconcile the oracle instance**

```bash
pgrep -a oracle_gui
```

If any instance is running against a ROM other than `/home/volence/sonic_hacks/aeon/s4.debug.bin`,
kill it — a stale instance means debugging the wrong binary:

```bash
pkill -x oracle_gui; sleep 1; pgrep -a oracle_gui
```

Expected after: no output.

- [ ] **Step 3: Build the debug shape from scratch**

```bash
cd /home/volence/sonic_hacks/aeon
export SIGIL_BUILD=/home/volence/sonic_hacks/sigil/target/release/sigil
export SIGIL_EMIT=/home/volence/sonic_hacks/sigil/target/release/emit_sound_blob
rm -f s4.debug.bin s4.debug.lst
DEBUG=1 ./build.sh 2>&1 | tail -5
```

Expected: `built: sonic4 debug native ROM — crc=d792e8d6 len=711252`

If the CRC differs, master has moved since this plan was written. That is fine — record the
new CRC and use it consistently; do not proceed with a mismatch between what you build and
what oracle loads.

- [ ] **Step 4: Re-derive the symbols rather than trusting this document**

```bash
cd /home/volence/sonic_hacks/aeon
grep -E "^(Replay_OJZ_Fixture|Replay_OJZ_Slide_Fixture|Replay_Ptr|Replay_Done|Input_Source|Logic_Tick|GameState_OJZScroll_Init) " s4.debug.lst
```

Expected: the eight symbols with addresses. **Write the values you get into your working
notes and use those**, not the table above.

- [ ] **Step 5: Verify the packer works and dump the current fixture**

```bash
cd /home/volence/sonic_hacks/aeon
python3 tools/replay_pack.py --selftest
python3 tools/replay_pack.py dump games/sonic4/data/replays/ojz_fixture.bin
```

Expected: `replay_pack selftest: PASS`, then a dump showing **1721 ticks, 27 checkpoints**,
`core_hash 0x7054d28b`, and a run list beginning `tick 0 byte 0x00 x1024`.

If the selftest does not pass, STOP — every later step depends on this decoder.

- [ ] **Step 6: Create the working directory and a pristine ROM copy**

```bash
SCRATCH=/tmp/claude-1000/-home-volence-sonic-hacks-aeon/0b00eff7-7d60-4ddc-affe-bf2e8f16146d/scratchpad/restamp
mkdir -p "$SCRATCH"
cp /home/volence/sonic_hacks/aeon/s4.debug.bin "$SCRATCH/work.bin"
cp /home/volence/sonic_hacks/aeon/s4.debug.bin "$SCRATCH/pristine.bin"
ls -la "$SCRATCH"
```

- [ ] **Step 7: Commit nothing; this task produces no repo changes**

No commit. This task exists to make the next six honest.

---

## Task 2: Baseline the failure and locate every checkpoint byte offset

**Files:**
- Create: `$SCRATCH/offsets.txt`

- [ ] **Step 1: Compute each checkpoint's byte offset inside the fixture, and inside the ROM**

The re-stamp patches 4-byte payloads. This step produces the exact addresses to patch. Write
and run:

```bash
cd /home/volence/sonic_hacks/aeon
SCRATCH=/tmp/claude-1000/-home-volence-sonic-hacks-aeon/0b00eff7-7d60-4ddc-affe-bf2e8f16146d/scratchpad/restamp
python3 - <<'PY' | tee "$SCRATCH/offsets.txt"
import sys
sys.path.insert(0, '/home/volence/sonic_hacks/aeon/tools')
blob = open('/home/volence/sonic_hacks/aeon/games/sonic4/data/replays/ojz_fixture.bin','rb').read()

ROM_BASE = 0xA1DA0          # Replay_OJZ_Fixture — RE-DERIVE from s4.debug.lst
HDR = 20
i = HDR
tick = 0
print(f"{'ring':>6} {'Logic_Tick':>11} {'file_off':>9} {'rom_off':>9} {'expected':>10}")
while i < len(blob):
    b = blob[i]
    if b != 0xFF:
        tick += blob[i+1] + 1
        i += 2
        continue
    op = blob[i+1]
    if op == 0x00:
        print(f"{'END':>6} {tick:>11} {i:>9}")
        break
    if op == 0x01:
        payload_off = i + 2
        h = int.from_bytes(blob[payload_off:payload_off+4], 'big')
        print(f"{tick:>6} {tick+2:>11} {payload_off:>9} {ROM_BASE+payload_off:>9X} {h:08X}")
        i += 6
PY
```

Expected: 27 rows, the first at ring 0, the last at ring 1664, and the row for ring **1280**
showing expected `1F420103`. If that value is not `1F420103`, the fixture on disk is not the
one this plan was written against — STOP and re-establish the baseline.

- [ ] **Step 2: Launch oracle on the working ROM**

```bash
/home/volence/sonic_hacks/oracle/linux-port/build/oracle_gui \
  /tmp/claude-1000/-home-volence-sonic-hacks-aeon/0b00eff7-7d60-4ddc-affe-bf2e8f16146d/scratchpad/restamp/work.bin &
sleep 3; pgrep -a oracle_gui
```

Expected: exactly one PID, running `work.bin`.

- [ ] **Step 3: Arm playback and run** (MCP, controller only)

Use these calls in order. `Replay_Ptr` = `Replay_OJZ_Fixture + 20` (the body, past the header).

```
emulator_breakpoint_add   addr=0xA1734        # GameState_OJZScroll_Init, BEFORE reload
emulator_reload_rom
emulator_wait_for_break
emulator_write_memory     addr=0xFF8040 value=662964 width=4    # Replay_Ptr = $A1DB4
emulator_write_memory     addr=0xFF803A value=1      width=1    # Input_Source = PLAYBACK
emulator_breakpoint_clear
emulator_resume
```

> **`value` is DECIMAL — convert carefully and always read back.** `$A1DB4` is **662964**.
> An earlier revision of this plan carried 662452, which is `$A1BB4` — a wrong pointer that
> the emulator accepts silently and that would have replayed garbage. Verify before resuming:
>
> ```
> emulator_read_memory addr=0xFF8040 len=4     # expect 000A1DB4
> emulator_read_memory addr=0xA1DA0    len=24  # expect 41525030 ... "ARP0" + header
> ```
>
> The second read is the stronger check: bytes 0-3 are `ARP0`, 6-9 are the tick count
> (`000006B9` = 1721), 10-13 the core hash, and offset 20 must be `FF 01` — the ring-0
> checkpoint escape, which is precisely where `Replay_Ptr` should land.

Then poll — **do not add a watchpoint on `Replay_Done`, it wedges the emulator**:

```
emulator_read_memory addr=0xFF803C width=1      # Replay_Done
emulator_status                                  # symbol_at_pc
```

- [ ] **Step 4: Read the trap**

When `emulator_status` shows `symbol_at_pc` at `ErrorHandlerBlob` (this presents as a hang —
`running=true`, `Logic_Tick` frozen — which is expected, not a failure):

```
emulator_screenshot
```

Read `d0` (actual hash), `d1` (`Logic_Tick`), `d2` (expected hash) off the MD Debugger's
register dump in the image.

> **Do NOT use `emulator_registers` here — it returns the wrong values.** Measured this
> session: by the time you can query, the handler is ~3630 bytes deep into
> `ErrorHandlerBlob` and has already clobbered `d0`-`d2` drawing its own screen (a live read
> returned `d0=FFFFFF00, d1=FFFFFF00, d2=00000004`). The trap-time values survive **only** on
> the displayed dump, which the MD Debugger captured at exception entry. The screenshot is
> the instrument.
>
> Cross-check cheaply with `emulator_read_memory addr=0xFF8004 len=4` (`Logic_Tick`), which
> must equal the `d1` you read off the screen.

Expected: `d1 = 0x502` (1282), `d2 = 0x1F420103`. Record whatever `d0` actually is — the
note says `BBB93779`, and this is the first time it is being independently measured.

- [ ] **Step 5: Write the baseline into the evidence note**

```bash
SCRATCH=/tmp/claude-1000/-home-volence-sonic-hacks-aeon/0b00eff7-7d60-4ddc-affe-bf2e8f16146d/scratchpad/restamp
printf 'ring 1280 (tick 1282): expected %s actual %s\n' "1F420103" "<d0 you measured>" >> "$SCRATCH/harvest.txt"
cat "$SCRATCH/harvest.txt"
```

---

## Task 3: Positive control — prove the trap can fire for the right reason

A gate you have never seen fail is not a gate. Before trusting a green run later, confirm the
comparator actually bites on a hash you know is wrong.

**Files:**
- Modify: `$SCRATCH/work.bin` (working copy only)

- [ ] **Step 1: Doctor checkpoint ring 0 in the working ROM**

Ring 0's ROM offset comes from Task 2's table (it is the first checkpoint row).

```bash
SCRATCH=/tmp/claude-1000/-home-volence-sonic-hacks-aeon/0b00eff7-7d60-4ddc-affe-bf2e8f16146d/scratchpad/restamp
python3 - <<'PY'
import os
p = os.environ.get('SCRATCH') or '/tmp/claude-1000/-home-volence-sonic-hacks-aeon/0b00eff7-7d60-4ddc-affe-bf2e8f16146d/scratchpad/restamp'
rom = bytearray(open(p + '/work.bin','rb').read())
OFF = 0xA1DB4 + 2 + 2      # ring-0 checkpoint payload — USE Task 2's measured rom_off
before = bytes(rom[OFF:OFF+4])
rom[OFF:OFF+4] = b'\xDE\xAD\xBE\xEF'
open(p + '/work.bin','wb').write(rom)
print('patched ring-0 payload', before.hex(), '->', 'deadbeef')
PY
```

- [ ] **Step 2: Re-run playback and confirm the trap fires at tick 2, not 1282**

Repeat Task 2 Step 3's MCP sequence, then read registers.

Expected: `REPLAY DESYNC` with `d1 = 2` (ring 0 + 2) and `d2 = 0xDEADBEEF`.

If the run instead reaches tick 1282 as before, the comparator is not reading the bytes you
patched — your offset is wrong. STOP and re-derive it. **Everything downstream is worthless
if this step does not behave.**

- [ ] **Step 3: Restore the working ROM**

```bash
SCRATCH=/tmp/claude-1000/-home-volence-sonic-hacks-aeon/0b00eff7-7d60-4ddc-affe-bf2e8f16146d/scratchpad/restamp
cp "$SCRATCH/pristine.bin" "$SCRATCH/work.bin"
cmp "$SCRATCH/work.bin" "$SCRATCH/pristine.bin" && echo "restored clean"
```

Expected: `restored clean`.

---

## Task 4: Harvest the corrected hashes by iteration

Each cycle fixes exactly one checkpoint. Repeat until playback completes.

**Files:**
- Modify: `$SCRATCH/work.bin`, `$SCRATCH/harvest.txt`

- [ ] **Step 1: Patch the checkpoint that just trapped**

Using `d0` (actual) and `d1` (tick) from the most recent trap. `ring = d1 - 2`; find that
ring's `rom_off` in Task 2's table.

```bash
SCRATCH=/tmp/claude-1000/-home-volence-sonic-hacks-aeon/0b00eff7-7d60-4ddc-affe-bf2e8f16146d/scratchpad/restamp
python3 - "$SCRATCH" <<'PY' "0x<rom_off>" "0x<d0>"
import sys
scratch, off, val = sys.argv[1], int(sys.argv[2],16), int(sys.argv[3],16)
rom = bytearray(open(scratch+'/work.bin','rb').read())
old = int.from_bytes(rom[off:off+4],'big')
rom[off:off+4] = val.to_bytes(4,'big')
open(scratch+'/work.bin','wb').write(rom)
open(scratch+'/harvest.txt','a').write(f'{off:X} {old:08X} -> {val:08X}\n')
print(f'{off:X}: {old:08X} -> {val:08X}')
PY
```

- [ ] **Step 2: Re-run playback**

Repeat Task 2 Step 3's MCP sequence against the patched `work.bin` (the `emulator_reload_rom`
in that sequence picks up the edited file).

- [ ] **Step 3: Classify the outcome**

Poll `Replay_Done` (`$FF803C`) and `emulator_status`:

- **`Replay_Done == 0xFF`, no error screen** → playback completed. Go to Task 5.
- **`ErrorHandlerBlob` at `symbol_at_pc`** → another stale checkpoint. Read `emulator_registers`,
  append to `harvest.txt`, and return to Step 1 of this task.
- **Neither, and `Logic_Tick` is still advancing** → still running; keep polling. The full
  1721-tick run takes ~75-90 s wall.

- [ ] **Step 4: Sanity-check the harvest before leaving this task**

```bash
SCRATCH=/tmp/claude-1000/-home-volence-sonic-hacks-aeon/0b00eff7-7d60-4ddc-affe-bf2e8f16146d/scratchpad/restamp
cat "$SCRATCH/harvest.txt"; wc -l < "$SCRATCH/harvest.txt"
```

Every patched offset must be **at or above** ring 1280's offset. **If any harvested checkpoint
is below ring 1280, STOP and escalate** — checkpoints 0..1216 were passing, so a change there
means something other than the C4 spindash divergence is in play, and re-stamping it would
bury a real regression rather than record an intended one.

---

## Task 5: Apply the harvest to the fixture on disk and rebuild

**Files:**
- Modify: `games/sonic4/data/replays/ojz_fixture.bin`

- [ ] **Step 1: Snapshot the pre-change fixture for the later diff**

```bash
SCRATCH=/tmp/claude-1000/-home-volence-sonic-hacks-aeon/0b00eff7-7d60-4ddc-affe-bf2e8f16146d/scratchpad/restamp
cd /home/volence/sonic_hacks/aeon
cp games/sonic4/data/replays/ojz_fixture.bin "$SCRATCH/ojz_fixture.before.bin"
python3 tools/replay_pack.py dump games/sonic4/data/replays/ojz_fixture.bin > "$SCRATCH/dump.before.txt"
```

- [ ] **Step 2: Apply every harvested hash to the fixture file**

The fixture's `file_off` is `rom_off - ROM_BASE` (both are in Task 2's table).

```bash
SCRATCH=/tmp/claude-1000/-home-volence-sonic-hacks-aeon/0b00eff7-7d60-4ddc-affe-bf2e8f16146d/scratchpad/restamp
cd /home/volence/sonic_hacks/aeon
python3 - <<'PY'
import os
scratch = '/tmp/claude-1000/-home-volence-sonic-hacks-aeon/0b00eff7-7d60-4ddc-affe-bf2e8f16146d/scratchpad/restamp'
ROM_BASE = 0xA1DA0          # RE-DERIVE from s4.debug.lst
path = 'games/sonic4/data/replays/ojz_fixture.bin'
fx = bytearray(open(path,'rb').read())
n = 0
for line in open(scratch + '/harvest.txt'):
    line = line.strip()
    if '->' not in line or line.startswith('ring'):
        continue
    off_s, old_s, _, new_s = line.split()
    off = int(off_s,16) - ROM_BASE
    fx[off:off+4] = int(new_s,16).to_bytes(4,'big')
    n += 1
open(path,'wb').write(fx)
print(f'applied {n} checkpoint hashes')
PY
```

- [ ] **Step 3: Verify the length did not change — this is what keeps the parcel aeon-only**

```bash
SCRATCH=/tmp/claude-1000/-home-volence-sonic-hacks-aeon/0b00eff7-7d60-4ddc-affe-bf2e8f16146d/scratchpad/restamp
cd /home/volence/sonic_hacks/aeon
stat -c%s games/sonic4/data/replays/ojz_fixture.bin "$SCRATCH/ojz_fixture.before.bin"
```

Expected: both `272`. **If they differ, STOP** — a length change moves `EndOfRom` and drags in
the sigil repin/refreeze ritual this parcel is designed to avoid.

- [ ] **Step 4: Verify only hash payloads changed, and the input stream is untouched**

```bash
SCRATCH=/tmp/claude-1000/-home-volence-sonic-hacks-aeon/0b00eff7-7d60-4ddc-affe-bf2e8f16146d/scratchpad/restamp
cd /home/volence/sonic_hacks/aeon
python3 tools/replay_pack.py dump games/sonic4/data/replays/ojz_fixture.bin > "$SCRATCH/dump.after.txt"
diff "$SCRATCH/dump.before.txt" "$SCRATCH/dump.after.txt"
```

Expected: differences confined to checkpoint hash values at ring >= 1280. **The run list
(`tick N byte 0xXX xM` lines) must be byte-for-byte identical**, as must `tick_count` (1721)
and the checkpoint count (27). Any change to the input stream means this stopped being a
re-stamp and the coverage claim no longer holds — STOP.

- [ ] **Step 5: Rebuild and confirm the ROM changed only where expected**

```bash
cd /home/volence/sonic_hacks/aeon
export SIGIL_BUILD=/home/volence/sonic_hacks/sigil/target/release/sigil
export SIGIL_EMIT=/home/volence/sonic_hacks/sigil/target/release/emit_sound_blob
rm -f s4.debug.bin s4.debug.lst && DEBUG=1 ./build.sh 2>&1 | grep -E "built:|^error"
```

Expected: `len=711252` unchanged, `crc` **different** from `d792e8d6` (the hashes changed).

- [ ] **Step 6: Commit**

```bash
cd /home/volence/sonic_hacks/aeon
git add games/sonic4/data/replays/ojz_fixture.bin
git commit -m "fix(replay): re-stamp ojz_fixture checkpoints stale since the Knuckles C4 merge

Only the 4-byte checkpoint hash payloads at ring >= 1280 change; the input
stream, tick count (1721) and checkpoint count (27) are byte-identical, so the
fixture's coverage is inherited rather than re-established and the fixture's
length is unchanged (no EndOfRom movement, no sigil repin).

The divergence was intended behaviour, not a regression: C4 changed spindash
dust, the line-0 palette and EnsureStanding, and the fixture drives a spindash
charge at ring 1212 (0x02 x25 then 0x22). The hash is address-free by contract
(replay.emp:7-16, :49-64), so a layout break would have desynced at checkpoint
0, not at 1280."
```

---

## Task 6: Measure the slide fixture, and re-stamp it only if red

Its status is **unmeasured** — no note reports on it. Do not assume either way.

**Files:**
- Modify (conditionally): `games/sonic4/data/replays/ojz_slide_fixture.bin`

- [ ] **Step 1: Refresh the working ROM from the newly built one**

```bash
SCRATCH=/tmp/claude-1000/-home-volence-sonic-hacks-aeon/0b00eff7-7d60-4ddc-affe-bf2e8f16146d/scratchpad/restamp
cp /home/volence/sonic_hacks/aeon/s4.debug.bin "$SCRATCH/work.bin"
cp /home/volence/sonic_hacks/aeon/s4.debug.bin "$SCRATCH/pristine.bin"
grep -E "^Replay_OJZ_Slide_Fixture " /home/volence/sonic_hacks/aeon/s4.debug.lst
```

- [ ] **Step 2: Run the slide fixture**

Same MCP sequence as Task 2 Step 3, but `Replay_Ptr` = `Replay_OJZ_Slide_Fixture + 20`
= `$A1EB0 + $14` = **`$A1EC4` = 663236 decimal** for the build this plan was written against.
Re-derive it, and read it back — see the decimal warning in Task 2 Step 3. (An earlier
revision said 662724, which is `$A1EC4` miscomputed.)

- [ ] **Step 3: Branch on the result**

- **`Replay_Done == 0xFF`** → the slide fixture is green. Record that in the evidence note and
  skip to Task 7.
- **`REPLAY DESYNC`** → re-run Tasks 2 (offsets, with `ROM_BASE` = the slide fixture's address
  and 37 checkpoints), 4 and 5 against `ojz_slide_fixture.bin`, expecting **336** bytes and
  **2350** ticks in the length and dump checks.

> **Extra caution if the slide fixture is red.** Its whole purpose is proving
> `EntityWindow_Slide` fires in all four crossing directions
> (`games/sonic4/test/replay_fixture.emp:19-35`). A re-stamp that silently records a run in
> which fewer crossings happened would be green and testing nothing. Before accepting it,
> confirm from the dump that the input stream is unchanged — the crossings are a property of
> the stream, so an identical stream preserves them.

---

## Task 7: Falsifiable verification

"The fixture is green" is true by construction after a re-stamp. These are the checks that
are not.

- [ ] **Step 1: Green on the ROM it was stamped against (necessary, not sufficient)**

Re-run Task 2 Step 3 against the freshly built `s4.debug.bin`.
Expected: `Replay_Done == 0xFF`, no error screen, gameplay live afterwards.

- [ ] **Step 2: Green on an UNRELATED already-merged commit**

This is the check that proves the fixture is not tuned to one build. Use a worktree so master
is untouched:

```bash
cd /home/volence/sonic_hacks/aeon
git worktree add /tmp/claude-1000/-home-volence-sonic-hacks-aeon/0b00eff7-7d60-4ddc-affe-bf2e8f16146d/scratchpad/xcheck 2f047e3 2>/dev/null || \
  git worktree add /tmp/claude-1000/-home-volence-sonic-hacks-aeon/0b00eff7-7d60-4ddc-affe-bf2e8f16146d/scratchpad/xcheck HEAD~5
cd /tmp/claude-1000/-home-volence-sonic-hacks-aeon/0b00eff7-7d60-4ddc-affe-bf2e8f16146d/scratchpad/xcheck
cp /home/volence/sonic_hacks/aeon/games/sonic4/data/replays/ojz_fixture.bin games/sonic4/data/replays/
SIGIL_BUILD=/home/volence/sonic_hacks/sigil/target/release/sigil \
SIGIL_EMIT=/home/volence/sonic_hacks/sigil/target/release/emit_sound_blob \
DEBUG=1 ./build.sh 2>&1 | grep -E "built:|^error"
```

Then run the fixture against that ROM (re-derive its symbols from its own `s4.debug.lst` —
they will differ).

Expected: `Replay_Done == 0xFF`.

> If it desyncs here, that is **informative, not necessarily fatal**: the older commit may
> genuinely predate a behaviour change. Record which checkpoint and reason about whether the
> behavioural delta between the two commits explains it. Do not silently re-stamp against the
> older build.

- [ ] **Step 3: Clean up the worktree**

```bash
cd /home/volence/sonic_hacks/aeon
git worktree remove /tmp/claude-1000/-home-volence-sonic-hacks-aeon/0b00eff7-7d60-4ddc-affe-bf2e8f16146d/scratchpad/xcheck --force
git worktree list
```

- [ ] **Step 4: Write the evidence note**

Create `docs/superpowers/notes/2026-08-13-replay-net-restamp-ab.md` recording: the measured
baseline (`d0`/`d1`/`d2` from Task 2), the positive-control result from Task 3, every harvested
checkpoint from Task 4, the before/after dump diff, the slide fixture's measured status, both
Task 7 legs, and the ROM CRCs before and after. Include the corrected fixture statistics
(1721/27/272 and 2350/37/336) so the next person does not inherit the stale numbers.

- [ ] **Step 5: Commit**

```bash
cd /home/volence/sonic_hacks/aeon
git add docs/superpowers/notes/2026-08-13-replay-net-restamp-ab.md
git commit -m "docs(replay): evidence for the P3 Parcel 0 re-stamp"
```

---

## Task 8: Correct the documentation rot this exposed

Four documents send the reader to a runbook that does not exist, and one note's numbers are
all stale. Left alone, the next person repeats this session's dead end.

**Files:**
- Modify: `docs/superpowers/specs/2026-08-13-effects-p3-design.md`
- Modify: `docs/superpowers/notes/2026-08-09-replay-net-rerecord-ab.md`
- Modify: `docs/superpowers/2026-08-13-effects-p2-handoff.md`
- Modify: `docs/superpowers/2026-08-12-next-session-handoff.md`

- [ ] **Step 1: Fix the spec's false citation**

In `docs/superpowers/specs/2026-08-13-effects-p3-design.md` §2.0, replace the sentence
directing the reader to "the probe-ROM logger route per
`docs/superpowers/notes/2026-08-09-replay-net-rerecord-ab.md`" with:

```markdown
Re-stamp by iterating against a patched ROM image (the runbook is
`docs/superpowers/plans/2026-08-13-replay-net-restamp.md`). Note that the
"probe-ROM logger" several docs cite in the 2026-08-09 note **is not in that
note** — the technique is sketched in `notes/2026-08-05-sst-fold-ab.md:27-38`
and was never committed as code. Re-RECORDING is not an option regardless: the
fixture's stream uses BUTTON_C in four runs (including the spindash rev inside
the desyncing region) and the oracle driver cannot press `c`.
```

- [ ] **Step 2: Add a superseded banner to the 2026-08-09 note**

Insert immediately after that file's title:

```markdown
> **SUPERSEDED IN PART (2026-08-13).** Every fixture statistic, CRC and byte count below is
> stale — the fixtures were replaced twice after this was written (`f3537d44`, `5129060c`).
> Measured truth: `ojz_fixture.bin` 1721 ticks / 27 checkpoints / 272 B;
> `ojz_slide_fixture.bin` 2350 ticks / 37 checkpoints / 336 B. Use
> `python3 tools/replay_pack.py dump <fixture>` as the source of truth.
> This note also does NOT contain the "probe-ROM logger" runbook that several later
> documents cite it for; see `notes/2026-08-05-sst-fold-ab.md:27-38`.
```

- [ ] **Step 3: Fix the two handoff citations**

In both `docs/superpowers/2026-08-13-effects-p2-handoff.md` and
`docs/superpowers/2026-08-12-next-session-handoff.md`, change each "probe-ROM logger per
`notes/2026-08-09-replay-net-rerecord-ab.md`" reference to point at this plan instead.

- [ ] **Step 4: Verify no live citation survives**

```bash
cd /home/volence/sonic_hacks/aeon
grep -rn "probe-ROM logger" docs/ | grep -v "2026-08-05-sst-fold-ab" | grep -v "restamp"
```

Expected: no output, or only lines that explicitly say the runbook does not exist.

- [ ] **Step 5: Commit**

```bash
cd /home/volence/sonic_hacks/aeon
git add docs/superpowers/specs/2026-08-13-effects-p3-design.md \
        docs/superpowers/notes/2026-08-09-replay-net-rerecord-ab.md \
        docs/superpowers/2026-08-13-effects-p2-handoff.md \
        docs/superpowers/2026-08-12-next-session-handoff.md
git commit -m "docs(replay): correct a runbook citation four docs inherited

The probe-ROM logger is not in the 2026-08-09 note (grep -n probe exits 1); it is
sketched in notes/2026-08-05-sst-fold-ab.md:27-38 and was never committed as code.
Also banners the 2026-08-09 note's fixture statistics, which have been stale since
the fixtures were replaced twice after it was written."
```

---

## Task 9: Close the hole that let master stay red silently

The net has **zero** automated representation. A structural test cannot catch a desync (that
needs the emulator), but it catches a corrupt or truncated repack, which is the failure this
parcel could plausibly introduce.

**Files:**
- Create: `tools/test_replay_fixture.py`
- Modify: `docs/DEFERRED_WORK.md`

- [ ] **Step 1: Write the failing test**

```python
"""Structural integrity of the committed replay fixtures.

This does NOT run the replay net — that needs the emulator and a human (see
docs/superpowers/plans/2026-08-13-replay-net-restamp.md). It catches a corrupt,
truncated, or mis-packed fixture, which is the failure a re-stamp can introduce.
"""
import pathlib
import sys

import pytest

TOOLS = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
REPLAYS = TOOLS.parent / "games" / "sonic4" / "data" / "replays"

import replay_pack  # noqa: E402


@pytest.mark.parametrize(
    "name,size,ticks,checkpoints",
    [
        ("ojz_fixture.bin", 272, 1721, 27),
        ("ojz_slide_fixture.bin", 336, 2350, 37),
    ],
)
def test_fixture_structure(name, size, ticks, checkpoints):
    path = REPLAYS / name
    blob = path.read_bytes()
    assert len(blob) == size, f"{name} length changed: EndOfRom moves, sigil repin required"

    raw, checks, core_hash, tick_count, seed, flags = replay_pack.decode_stream(blob)
    assert tick_count == ticks
    assert len(checks) == checkpoints
    assert len(raw) == ticks
    assert seed == 0, "rng_seed must stay 0 until an RNG exists"

    # Checkpoints sit on the 64-tick ring boundary, starting at 0.
    for i, (ring, _hash) in enumerate(checks):
        assert ring == i * 64, f"{name} checkpoint {i} at ring {ring}, expected {i * 64}"


def test_fixture_c_button_runs_are_preserved():
    """The spindash rev at ring 1237/1248 uses BUTTON_C, which cannot be driven
    interactively. If these runs ever vanish, the fixture was RE-RECORDED rather
    than re-stamped and its coverage claim no longer holds."""
    blob = (REPLAYS / "ojz_fixture.bin").read_bytes()
    raw, _checks, _core, _ticks, _seed, _flags = replay_pack.decode_stream(blob)
    BUTTON_C = 0x20
    assert raw[1237] & BUTTON_C, "spindash rev at ring 1237 lost its C press"
    assert raw[1248] & BUTTON_C, "spindash rev at ring 1248 lost its C press"
    assert all(b == 0x02 for b in raw[1212:1237]), "the ring-1212 DOWN hold changed"
```

- [ ] **Step 2: Run it to verify it passes against the re-stamped fixtures**

```bash
cd /home/volence/sonic_hacks/aeon
python3 -m pytest tools/test_replay_fixture.py -v
```

Expected: 3 passed.

(`decode_stream`'s contract is verified: `tools/replay_pack.py:114-117` returns
`(raw, checks, core_hash, tick_count, seed, flags)` with `checks` as `[(ring_index, hash)]`,
which is exactly what the test unpacks.)

- [ ] **Step 3: Prove the test can fail**

```bash
cd /home/volence/sonic_hacks/aeon
cp games/sonic4/data/replays/ojz_fixture.bin /tmp/fx.bak
python3 -c "
p='games/sonic4/data/replays/ojz_fixture.bin'
b=bytearray(open(p,'rb').read()); b[-1]=0xAA; b.append(0)
open(p,'wb').write(b)"
python3 -m pytest tools/test_replay_fixture.py -v 2>&1 | tail -5
cp /tmp/fx.bak games/sonic4/data/replays/ojz_fixture.bin && rm /tmp/fx.bak
git status --short games/sonic4/data/replays/
```

Expected: the length assertion fails, then the restore leaves the fixture unmodified.

- [ ] **Step 4: Record the real gap in DEFERRED_WORK**

Add an entry noting that the replay net has no automated runner — it lives only in a manual
oracle procedure, which is how master stayed red without any gate reporting it. Name the two
candidate fixes (a headless oracle runner invoked from `test.sh`, or a committed re-stamp tool
that makes the manual loop cheap) and cite this plan.

- [ ] **Step 5: Commit**

```bash
cd /home/volence/sonic_hacks/aeon
git add tools/test_replay_fixture.py docs/DEFERRED_WORK.md
git commit -m "test(replay): structural gate for the fixtures + record the automation gap

Cannot catch a desync (that needs the emulator) but catches a corrupt or
truncated repack, and pins the BUTTON_C runs that prove the fixture was
re-stamped rather than re-recorded. The net having no automated runner at all
is recorded in DEFERRED_WORK — that is why master stayed red silently."
```

---

## Done when

- [ ] `ojz_fixture.bin` replays to `Replay_Done == $FF` on current master's `s4.debug.bin`
- [ ] The same fixture replays green on an unrelated already-merged commit (Task 7 Step 2)
- [ ] The positive control fired (Task 3) — the trap is known to bite
- [ ] The input stream, tick count and checkpoint count are byte-identical to before
- [ ] Both fixture files are unchanged in length (272 / 336) — no sigil ritual needed
- [ ] `ojz_slide_fixture.bin` measured, and re-stamped only if it was red
- [ ] Evidence note written; false runbook citations corrected in four documents
- [ ] `python3 -m pytest tools/test_replay_fixture.py` passes and is known to be able to fail
- [ ] `python3 -m pytest -q` still reports 941 passed + the 3 new tests
