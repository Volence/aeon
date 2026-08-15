# Byte-Level Capture + Effects Gates — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the effects suite's hand-driven oracle rituals into a committed, re-runnable gate by teaching `ab_runner` to capture and diff actual BYTES, then expressing this parcel's three-state raster matrix as a scene.

**Architecture:** `linux-port/harness/ab_runner.py` already boots isolated headless Oracle instances, replays a deterministic `poke`/`press`/`run_frames` scene, and prints a gated OLD-vs-NEW table. It captures region HASHES, which answer "did it change" but not "what is it". A `memory_read` capture reports the bytes themselves, so a gate can assert the arm word is `$8A61` rather than that some hash moved.

**Tech Stack:** Python 3 (`ab_runner`, the oracle control-socket bus client), JSON scenes, aeon `.lst` symbol tables.

**Repos:** code in `oracle` (`linux-port/harness/`), scene + gate + evidence in `aeon`. Two repos, so **two commits, and neither is a byte-moving parcel** — no repin/refreeze ritual applies.

---

## Why this shape, and what was NOT built

The 2026-08-16 work order scoped a `replay_runner --dump-frames` parcel in `oracle-next`. That was
retargeted to `oracle` (owner ruling: oracle-next is not ready), and the survey then found most of
the parcel already exists:

| the work order wanted | status in `oracle` |
|---|---|
| headless frame dump | `oracle_cli --frames-dir` writes `frameNNNN.png` per frame |
| state control (`--poke`) | `ab_runner` scenes: `poke` / `press` / `run_frames`, by addr or symbol |
| `--expect-identical` control | `ab_runner --selfcheck` (exit 2 = the SCENE is nondeterministic) |
| paired report as the artifact | `ab_runner`'s table + per-side `hashes.json` |
| `replay_framediff` over pixels | **not built, and deliberately not built here** |

**Pixels are not gateable on oracle, by construction.** `ab_runner`'s own docstring root-causes it:
the VDP renders on a worker thread (`S315_5313::RenderThread`) draining an async queue, and the
framebuffer the GUI copies is not anchored to the deterministic `ExecuteSystemStep` count, so two
identical runs can capture a one-render-frame-off image. Measured independently while surveying:
three identical `oracle_cli` runs of `s4.debug.bin` agreed on 26 of 28 frames and differed on frames
2 and 5 by 8.9% and 25.0% of pixels (rows 134-154 and 98-153) — with the frame tokens advancing by
exactly 1 in all three runs, so the frames were correctly aligned and the CONTENT differed.

The named fix is an emulator-side change (`OpScreenshot` waits for `_pendingRenderOperationCount == 0`,
or renders synchronously from committed VDP state). Until that lands, a framediff instrument would
be a careful measuring tool pointed at a nondeterministic source. **That is the follow-on parcel,
and it is the prerequisite for pixels — not this one.**

---

## File Structure

| file | responsibility |
|---|---|
| `oracle/linux-port/harness/ab_runner.py` | gains a `memory_read` capture: bytes in the sidecar, byte-level diff in the table |
| `oracle/linux-port/harness/memory_read_test.py` | new: proves the capture is wired and non-vacuous |
| `aeon/tools/scenes/effects_raster_states.json` | new: the three-state matrix as a scene |
| `aeon/tools/effects_scene_assert.py` | new: the GATE — asserts expected bytes from a sidecar |
| `aeon/docs/benchmarks/effects-p3-removal/GATE-EVIDENCE.md` | gains the re-derivation section |

---

## Task 1: `memory_read` capture in `ab_runner`

**Files:**
- Modify: `oracle/linux-port/harness/ab_runner.py` — `load_scene`, `_execute`, `capture_items`, `compare`, `print_table`, the module docstring's scene-format block

- [ ] **Step 1: Write the failing test first**

Create `oracle/linux-port/harness/memory_read_test.py`, modelled on the existing
`memory_hash_test.py` (read it first — match its boot/socket/teardown idiom exactly; do not invent a
new harness shape). The test must:

1. Boot one instance on a known ROM.
2. Run a scene with a `memory_read` region over a symbol whose contents the test can predict —
   use `Raster_Buf_A` with `len: 16` after a short `run_frames`, and assert the returned hex is
   32 characters of `[0-9a-f]`.
3. **Poke a byte inside that region, re-capture, and assert the reported bytes CHANGED at exactly
   the poked offset** — this is the non-vacuity half, and it is what distinguishes a wired capture
   from one that returns a constant.

- [ ] **Step 2: Run it and watch it fail**

```bash
cd /home/volence/sonic_hacks/oracle && python3 linux-port/harness/memory_read_test.py
```

Expected: FAIL — `memory_read` is not a recognised capture key, so `load_scene` raises `SceneError`.

- [ ] **Step 3: Accept and validate the scene key**

In `load_scene`, beside the existing `memory_hash` validation, add:

```python
    cap.setdefault("memory_read", [])
    seen_r = set()
    for r in cap["memory_read"]:
        nm = r.get("name")
        if not nm:
            raise SceneError("every memory_read region needs a name")
        if nm in seen_r:
            raise SceneError(f"duplicate memory_read region name: {nm}")
        seen_r.add(nm)
        if "addr" not in r and "symbol" not in r:
            raise SceneError(f"memory_read region {nm} needs addr or symbol")
        if "len" not in r:
            raise SceneError(f"memory_read region {nm} needs len")
        # A read region is meant to be READ BY A HUMAN in the table and asserted field-by-field
        # by a gate. A 64 KB region is a hash's job, not a read's: it would render an unreadable
        # table and an unreviewable diff. The ceiling is what keeps the two captures distinct.
        if not (1 <= int(r["len"]) <= 256):
            raise SceneError(
                f"memory_read region {nm}: len {r['len']} outside 1..256 — use memory_hash for "
                f"regions too large to read")
```

- [ ] **Step 4: Capture the bytes**

In `_execute`, after the `memory_hash` loop, add:

```python
    for r in cap.get("memory_read", []):
        params = {"len": r["len"]}
        if "symbol" in r:
            params["symbol"] = r["symbol"]
        else:
            params["addr"] = r["addr"]
        m = await b.call("emulator/read_memory", params)
        result["memory_read"][r["name"]] = {
            "addr": m.get("addr"), "len": m.get("len"), "bytes": m["bytes"],
        }
```

and add `"memory_read": {}` to the `result` initialiser beside `"memory_hash": {}`.

- [ ] **Step 5: Make the bytes a GATED comparison item**

In `capture_items`, after the `memory_hash` loop:

```python
    for name in cap.get("memory_read", {}):
        items.append((f"read:{name}",
                      lambda c, n=name: c["memory_read"][n]["bytes"], False))
```

`False` is the advisory flag — these are GATED, exactly like `memory_hash`. Bytes read committed
emulator state through the same deterministic path a hash does; only the framebuffer is advisory.

- [ ] **Step 6: Show WHAT differs, not just THAT it differs**

This is the whole point of the task. In `print_table` (or a helper it calls), when a `read:` row
differs, print the differing byte offsets and both values beneath the row:

```python
def byte_diff_detail(old_hex: str, new_hex: str, limit: int = 8) -> list[str]:
    """Offsets where two hex byte-strings differ, as `+OFF old->new`, capped at `limit`.

    A hash tells a reviewer that something moved; this tells them WHICH byte and to what. That
    difference is the reason this capture exists: an effects gate needs to read an arm word
    ($8A61 -> $8ADB), not learn that a region's hash changed.
    """
    a = bytes.fromhex(old_hex); b = bytes.fromhex(new_hex)
    out = []
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            if len(out) == limit:
                out.append(f"... and {sum(1 for p, q in zip(a[i:], b[i:]) if p != q) - 0} more")
                break
            out.append(f"+{i:03X} {x:02X}->{y:02X}")
    if len(a) != len(b):
        out.append(f"LENGTH {len(a)} -> {len(b)}")
    return out
```

Call it for differing `read:` rows only. Keep the table itself one line per item; the detail goes
underneath, indented, so the table stays scannable.

- [ ] **Step 7: Run the test to green**

```bash
cd /home/volence/sonic_hacks/oracle && python3 linux-port/harness/memory_read_test.py
```

Expected: PASS, including the poke-changes-the-bytes half.

- [ ] **Step 8: Update the module docstring's scene-format block**

Add `memory_read` to the documented scene format beside `memory_hash`, and state the division of
labour in one line: **hash for "did this large region change", read for "what exactly is in this
small one"**. Also record the 1..256 ceiling and why.

- [ ] **Step 9: Commit (oracle repo)**

```bash
cd /home/volence/sonic_hacks/oracle
git add linux-port/harness/ab_runner.py linux-port/harness/memory_read_test.py
git commit -m "harness(ab_runner): memory_read capture — gate on bytes, not just a hash"
```

---

## Task 2: The effects scene

**Files:**
- Create: `aeon/tools/scenes/effects_raster_states.json`

- [ ] **Step 1: Write the scene**

Three anchor states cannot share one scene — each needs its own capture — so the scene drives the
channel to the state that matters most (the one this parcel created) and captures the live buffer.
Symbols come from the DEBUG shape's listing because `Debug_Scene_Freeze` exists only there.

```json
{
  "name": "effects_raster_suppressed",
  "symbols": "/home/volence/sonic_hacks/aeon/s4.debug.lst",
  "reset": true,
  "steps": [
    {"run_frames": 180},
    {"poke": {"symbol": "Debug_Scene_Freeze", "value": 1, "width": 1}},
    {"poke": {"symbol": "Effects_World_Y", "value": 374, "width": 2}},
    {"run_frames": 3}
  ],
  "capture": {
    "screenshot": false,
    "state_hash": true,
    "memory_read": [
      {"name": "raster_buf_a",  "symbol": "Raster_Buf_A", "len": 48},
      {"name": "raster_buf_b",  "symbol": "Raster_Buf_B", "len": 48},
      {"name": "active_buf",    "symbol": "Raster_Active_Buf", "len": 4},
      {"name": "screen_l",      "symbol": "Effects_Screen_L", "len": 8}
    ]
  }
}
```

**Both buffers are captured on purpose.** The builder swaps `Raster_Active_Buf` every frame, so
which of A/B is live depends on frame parity; capturing both plus the pointer makes the scene
robust to that instead of silently reading the stale buffer. A gate resolves the live one from
`active_buf`.

`screenshot: false` because it is advisory here and costs a settle poll.

- [ ] **Step 2: Prove the scene is deterministic BEFORE trusting anything it says**

```bash
cd /home/volence/sonic_hacks/oracle && python3 linux-port/harness/ab_runner.py \
  --old /home/volence/sonic_hacks/aeon/s4.debug.bin \
  --new /home/volence/sonic_hacks/aeon/s4.debug.bin \
  --scene /home/volence/sonic_hacks/aeon/tools/scenes/effects_raster_states.json \
  --out /tmp/claude-1000/.../scratchpad/abgate --selfcheck
```

Expected: `[selfcheck] OK — scene is deterministic.` then `VERDICT: ALL EQUAL (gated)` (same ROM
both sides). **If selfcheck fails (exit 2), STOP** — a nondeterministic scene invalidates everything
downstream, and the cause is the scene, not the ROM.

- [ ] **Step 3: Commit (aeon repo)**

```bash
cd /home/volence/sonic_hacks/aeon && git add tools/scenes/effects_raster_states.json
git commit -m "tools(scenes): the raster suppressed-state scene, as an ab_runner fixture"
```

---

## Task 3: The gate

**Files:**
- Create: `aeon/tools/effects_scene_assert.py`

- [ ] **Step 1: Write the gate**

The hard line from the work order, restated because it is what keeps every future gate thin: **a
gate selects and asserts on REPORT fields; it never reads pixels, and it never re-implements the
measurement.** This reads a side's `hashes.json` and asserts the raster program's shape.

```python
#!/usr/bin/env python3
"""effects_scene_assert — assert a raster program's SHAPE from an ab_runner sidecar.

Reads one side's hashes.json (produced by ab_runner with a memory_read capture) and checks the
live raster buffer against expected words. It never touches the emulator and never reads a pixel:
the measurement is the harness's job, the verdict is this script's.

The buffer to read is resolved from Raster_Active_Buf, because Raster_BuildSchedule swaps buffers
every frame — reading a fixed buffer would sample the stale one on half of all frames.
"""
import json, sys, argparse

def words(hexstr):
    b = bytes.fromhex(hexstr)
    return [int.from_bytes(b[i:i+2], "big") for i in range(0, len(b) - 1, 2)]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sidecar")
    ap.add_argument("--expect-word", action="append", default=[],
                    metavar="INDEX=VALUE", help="e.g. 1=0x8ADB (repeatable)")
    ap.add_argument("--expect-absent", action="append", default=[], metavar="HEX",
                    help="a word that must NOT appear in the live buffer, e.g. 0x8C89")
    a = ap.parse_args()

    side = json.loads(open(a.sidecar).read())
    reads = side["memory_read"]
    active = int(reads["active_buf"]["bytes"], 16) & 0xFFFFFF
    buf_a = int(reads["raster_buf_a"]["addr"], 16) & 0xFFFFFF
    live = "raster_buf_a" if active == buf_a else "raster_buf_b"
    w = words(reads[live]["bytes"])

    bad = []
    for spec in a.expect_word:
        idx, val = spec.split("=")
        idx, val = int(idx, 0), int(val, 0)
        if idx >= len(w):
            bad.append(f"word {idx} is past the captured region ({len(w)} words)")
        elif w[idx] != val:
            bad.append(f"word {idx}: expected {val:#06x}, got {w[idx]:#06x}")
    for spec in a.expect_absent:
        val = int(spec, 0)
        if val in w:
            bad.append(f"word {val:#06x} is present at index {w.index(val)} but must be absent")

    print(f"live buffer: {live} @ {reads[live]['addr']}")
    print("  " + " ".join(f"{x:04X}" for x in w))
    for b in bad:
        print(f"FAIL: {b}", file=sys.stderr)
    if bad:
        return 1
    print(f"OK — {len(a.expect_word)} word(s) and {len(a.expect_absent)} absence(s) asserted")
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run it against the sidecar from Task 2**

```bash
python3 tools/effects_scene_assert.py /tmp/.../abgate/old/hashes.json \
  --expect-word 1=0x8ADB --expect-word 3=0x8AFF --expect-absent 0x8C89
```

Expected: `OK`. The three assertions are exactly this parcel's suppressed-state result — priming 0
schedules channel 1 directly, priming 1 parks, and the water record's `OP_SET_REG` word is gone.

- [ ] **Step 3: Prove the gate FAILS when it should**

Re-run with a deliberately wrong expectation (`--expect-word 1=0x8A61`, the mid-band value) and
confirm exit 1 with a message naming the word and both values. Quote both outcomes in the evidence.
A gate nobody has seen fail is a gate nobody knows is wired.

- [ ] **Step 4: Commit**

```bash
cd /home/volence/sonic_hacks/aeon && git add tools/effects_scene_assert.py
git commit -m "tools(gate): assert a raster program's shape from an ab_runner sidecar"
```

---

## Task 4: Re-derive this parcel's matrix through the tool

This is the definition of done. The work order's original one — reproduce P-b's row measurements —
was written for a pixel instrument; the current equivalent is the matrix this parcel measured by
hand, which is a strictly better target because the numbers are fresh and structural.

- [ ] **Step 1: Add mid-band and above-screen scenes**

Copy `effects_raster_states.json` twice, changing ONLY the `Effects_World_Y` poke and the name:
`244` (mid-band, `L` = 100) and `100` (above screen, `L` = -44). Same captures.

- [ ] **Step 2: Assert all three states**

| scene | assertion |
|---|---|
| suppressed (374) | word 1 = `0x8ADB`, word 3 = `0x8AFF`, `0x8C89` ABSENT |
| mid-band (244) | word 1 = `0x8A61`, word 3 = `0x8A79`, `0x8C89` PRESENT |
| above (100) | word 1 = `0x8A00`, `0x8C89` PRESENT |

The mid-band and above values come from `docs/benchmarks/effects-p3-removal/GATE-EVIDENCE.md`.
**Re-derive them from the formula rather than copying** — `arm = $8A00 | (this_fire - prev_fire - 1)`
— and if a derivation disagrees with the recorded number, the recorded number is what to doubt
first, then the code.

- [ ] **Step 3: Record the evidence**

Append a "re-derived through ab_runner" section to
`docs/benchmarks/effects-p3-removal/GATE-EVIDENCE.md`: the three scenes, the selfcheck result, the
asserted words, and the deliberate-failure output. State plainly that the hand-run oracle matrix and
the harness agree — or, if they disagree, STOP and report rather than adjusting either.

- [ ] **Step 4: Commit both repos**

---

## Task 5: Hand it forward

- [ ] **Step 1: Write the work order section**

`docs/superpowers/2026-08-18-next-session-handoff.md`: what shipped, and the two things this parcel
deliberately did not do —
1. **Pixels remain ungateable on oracle.** The fix is named and emulator-side
   (`OpScreenshot` waits for `_pendingRenderOperationCount == 0`, or renders synchronously from
   committed VDP state). The framediff instrument is worth building the day after that lands, not
   before. Include the measured boot-window numbers (frames 2 and 5; 8.9% / 25.0%; rows 134-154 and
   98-153; tokens advancing by exactly 1) so the next session does not re-measure them.
2. **`oracle_cli` was not extended.** It boots and runs; `ab_runner` drives the GUI build through
   the control socket. If a future gate wants a fully headless path with no GUI process,
   that is a separate parcel.

- [ ] **Step 2: Update `docs/BUGS.md`** with the oracle screenshot-determinism entry if one does not
already exist, citing `ab_runner.py`'s docstring as the root cause and this parcel's measurements as
the quantification.

- [ ] **Step 3: Commit and push both repos**

---

## Self-review against the brief

- Owner ruling "byte-level capture + adopt for effects gates" → Tasks 1-4.
- The work order's "gates may select and assert on report fields, never pixels" → Task 3's gate
  reads a JSON sidecar and nothing else.
- The work order's `--expect-identical` → already exists as `--selfcheck`; Task 2 Step 2 runs it
  before trusting any result, and treats its failure as a full stop.
- Definition of done → Task 4, re-deriving this parcel's own matrix.
- NOT in scope, and said so where a reader would look for it: the framediff instrument,
  `oracle_cli --poke`, and the render-anchoring fix.
