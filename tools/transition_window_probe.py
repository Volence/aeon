#!/usr/bin/env python3
"""transition_window_probe — does THIS tool sample inside a live parallax transition?

THE QUESTION IT ANSWERS, AND WHY IT IS ONE INSTRUMENT RATHER THAN AN EDIT PER TOOL.
A parallax scene does not install instantly. `Parallax_StartTransition` stages a target
and sets `Parallax_Transition_Frames` to PARALLAX_TRANS_DEFAULT (16), and the engine only
promotes the target into `Parallax_Current_Config` when that counter reaches 0
(engine/level/parallax.emp Step 1). A tool that samples inside that window reads the
OUTGOING scene's config and per-band scroll values lerped part-way to the incoming ones.

A transition is staged by CROSSING A REGION — `Parallax_CheckBoundary` is its only caller —
so any tool that moves the camera can open one, whether or not it names a parallax symbol.
That is why classifying by grep over `Parallax_*` misses tools: a tool that travels and
screenshots is exposed through the rendered frame and never spells the symbol.

So this runs the SUBJECT TOOL UNMODIFIED, under a shim on `aether.BusClient.call`, and
reads the machine's own counter immediately before every read the tool performs. The
verdict is a measurement off the running machine, not a reading of the tool's source.

NON-PERTURBING, AND THAT IS CHECKED RATHER THAN ASSUMED. The shim issues only
`emulator/read_memory`, which advances no frames and has no side effect on this bus, and
it re-enters itself under a guard so its own reads are not instrumented. The control is
the subject tool's stdout with and without the shim: they must be byte-identical. See the
sweep's report rows — `parallax_crossing_gate` was diffed both ways and came back IDENTICAL.

⚠ THE VALIDITY GATE IS LOAD-BEARING, AND WITHOUT IT THIS INSTRUMENT LIES.
Before the level runs, `Parallax_Transition_Frames` is uninitialised RAM. The first
un-gated run of this probe reported `frames=158` on 219 of 282 reads of a tool that is in
fact clean — 158 is not a possible value of a counter the engine only ever writes as 16 and
decrements. A read counts as INSIDE A WINDOW only when BOTH hold:
  * `1 <= frames <= 16`                    — the counter's entire live range, and
  * `Parallax_Current_Config` is an even pointer inside the ROM image
                                           — i.e. the level is actually running.
On the same tool that gate cut 282 reads to 74 live, of which 11 were genuinely in a window.

usage:  transition_window_probe.py <tool.py> [args for the tool ...]
        SHIM_OUT=<path.json> to write the machine-readable record.
"""
import sys, os, json, runpy, pathlib

TOOLS = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import suite_paths                                    # noqa: E402
suite_paths.add_client_path()
import aether                                         # noqa: E402

# 24-bit bus: the .lst's FFFFxxxx work-RAM addresses are masked to 0xFFFFFF, which is
# what every other tool in this tree does (`& 0xFFFFFF` in lst_symbol). Passing the
# unmasked value earns "[-32004] the 68000 bus is 24 bits wide".
FRAMES = 0xFF88F4          # Parallax_Transition_Frames  (byte)
CUR    = 0xFF88EC          # Parallax_Current_Config     (long)
CAM    = 0xFFA74C          # Camera_X                    (16.16; top word is the integer)

TRANS_DEFAULT = 16         # engine/system/constants.emp PARALLAX_TRANS_DEFAULT
ROM_MAX = 0xD0000          # any config pointer lives inside the image

READS = {"emulator/read_memory", "emulator/read_vram", "emulator/read_cram",
         "emulator/screenshot", "emulator/state_hash", "emulator/memory_hash",
         "emulator/read_vsram", "emulator/scanlines", "emulator/sprites",
         "emulator/pixel_attribution", "emulator/registers"}

_orig = aether.BusClient.call
_busy = {"n": 0}
REC = {"samples": [], "open_reads": 0, "total_reads": 0, "live_reads": 0,
       "preboot_reads": 0, "max_frames": 0, "cfgs": [], "err": None}


def _hex(r):
    b = r.get("bytes", "")
    return b[2:] if b.startswith("0x") else b


async def _peek(self):
    f = int(_hex(await _orig(self, "emulator/read_memory",
                             {"addr": hex(FRAMES), "len": 1}))[:2], 16)
    cfg = _hex(await _orig(self, "emulator/read_memory",
                           {"addr": hex(CUR), "len": 4}))[:8]
    cam = int(_hex(await _orig(self, "emulator/read_memory",
                               {"addr": hex(CAM), "len": 4}))[:4], 16)
    return f, cfg, cam


async def patched(self, method, params=None):
    if method in READS and _busy["n"] == 0:
        _busy["n"] = 1
        try:
            f, cfg, cam = await _peek(self)
            REC["total_reads"] += 1
            cfgv = int(cfg, 16)
            live = 0 < cfgv < ROM_MAX and cfgv % 2 == 0
            if live:
                REC["live_reads"] += 1
                REC["max_frames"] = max(REC["max_frames"], f if f <= TRANS_DEFAULT else 0)
                if cfg not in REC["cfgs"] and len(REC["cfgs"]) < 12:
                    REC["cfgs"].append(cfg)
                if 1 <= f <= TRANS_DEFAULT:
                    REC["open_reads"] += 1
                    if len(REC["samples"]) < 12:
                        REC["samples"].append({"method": method, "frames": f,
                                               "cur": cfg, "camx": cam})
            else:
                REC["preboot_reads"] += 1
        except Exception as e:                        # never fail the subject's run
            REC["err"] = repr(e)
        finally:
            _busy["n"] = 0
    return await _orig(self, method, params)


aether.BusClient.call = patched

if len(sys.argv) < 2:
    sys.exit(__doc__)
tool = sys.argv[1]
sys.argv = sys.argv[1:]
rc = 0
try:
    runpy.run_path(tool, run_name="__main__")
except SystemExit as e:
    rc = e.code if isinstance(e.code, int) else 0
except BaseException as e:
    REC["err"] = "%s: %s" % (type(e).__name__, e)
    rc = 99
REC["rc"] = rc
REC["tool"] = tool
out = os.environ.get("SHIM_OUT")
if out:
    pathlib.Path(out).write_text(json.dumps(REC, indent=1))
print("transition_window_probe: %s  reads=%d live=%d preboot=%d  IN-WINDOW=%d  maxFrames=%d"
      % (tool, REC["total_reads"], REC["live_reads"], REC["preboot_reads"],
         REC["open_reads"], REC["max_frames"]), file=sys.stderr)
sys.exit(rc)
