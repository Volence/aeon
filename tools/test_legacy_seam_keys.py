#!/usr/bin/env python3
"""Every key AND every value shape we send the legacy C++ server, against what it honours.

## The asymmetry, restated one level up from `test_wait_for_break_spelling.py`

That file pins ONE key (`timeout_ms`) because a rename against the legacy seam is silent. This
file is the same argument applied to the whole vocabulary, because the property that made the
rename silent is not a property of that key — **it is a property of the accessor**:

    bool has(k)          { return p && p->is_object() && p->contains(k) && !p->at(k).is_null(); }
    std::string get(k,d) { if (!has(k)) return d; ... }
    long long getInt(k,d){ if (!has(k)) return d; ... catch (...) { return d; } ... }
    uint32_t getU32(k,d) { return (uint32_t)getInt(k, (long long)d); }
    bool getBool(k,d)    { if (!has(k)) return d; ... }

There is no unknown-key rejection anywhere in `ControlSocket.cpp`. The Rust core
(`oracle-aether`) declares `unevaluatedProperties: false` and answers `-32602`, so a mistake
there fails in a minute. On the legacy server a mistake returns a success reply.

## TWO axes, because a spelling gate checks the cheaper half

**Axis 1 — spelling.** A key the handler never reads is silently ignored, and the caller gets
`{"ok": true}`. `emulator/write_vram` with `addres` writes VRAM at 0 and reports success.

**Axis 2 — value shape**, and this is the axis a spelling gate cannot see. `has()` returns true
for ANY present non-null value, so a perfectly-spelled key with the wrong JSON type also sails
past every guard in the file and lands on the accessor's fallback:

    {"layer": "plane_a", "enabled": "on"}   -> has("enabled") is TRUE, so the
                                               `if (!req.has("enabled")) return Error` guard
                                               passes; getBool's string arm accepts only
                                               "true"/"1"/"yes", so `on` is FALSE; the site
                                               then executes `*flag = !on` and MUTES the layer
                                               the caller asked to ENABLE.

`"True"`, `"TRUE"`, `"on"`, `1.0`-as-`"1.0"`, an array or an object all do it. So the pinned
contract carries `accepted_shapes` per key and not only a name.

## `guarded_by` is emitted, and it is not decoration

The table records, per key, whether a `req.has(k)` guard lexically encloses the read. Without
that column two very different classes render identically:

  * `z80_write.addr` (`:726`) and `write_vram.addr` (`:2140`) are read with NO guard above
    them. A misspelling there reaches the accessor default, address 0, and the write lands.
  * `write_memory.addr` (`:348`) is read inside `if (req.has("addr"))` in `ResolveAddrDetailed`.
    A misspelling there does NOT reach the accessor at all: the helper falls through to
    `symbol`, finds nothing, and returns `ErrorReply("need addr or symbol")`. It is LOUD.

Both are `getU32("addr")` with default 0 and only the guard column separates them. (The guard
still does nothing for axis 2: `{"addr": "0xZZZZ"}` passes `has()`, throws inside `stoll`, is
swallowed by `catch (...)`, and returns 0 on every one of these sites.)

## What each row asserts

  1. `test_send_sites_are_found_at_all`  — positive control on the client side; a detector that
     silently matches nothing makes every row below vacuous.
  2. `test_no_method_literal_escapes_the_extractor` — the other half of that control, and the
     sharper one: every `"emulator/<method>"` literal passed to a call must come back out of
     `send_sites()`. The first draft read only `args[0]` and therefore measured ZERO sites in
     `raster_frame_epoch_probe.py`, which makes eight of them through `_c(bus, method, params)`.
  3. `test_contract_matches_the_legacy_server` — re-derives the whole table from
     `ControlSocket.cpp` and compares it to `CONTRACT` below, so the pin cannot rot into folklore.
  4. `test_accessor_value_semantics_are_unchanged` — re-derives the four accessors' type
     branches (and `getBool`'s literal string set) from the struct body, so `SHAPES` below stays
     tied to the code it models.
  5. `test_parameter_read_population_is_closed` — pins the 63 accessor calls plus the one
     parameter (`buttons`) read outside the family = 64. A 65th means a new read MECHANISM
     appeared and rows 3-4 may be blind to it.
  6. `test_legacy_seam_keys_are_honoured`      — axis 1, over every legacy/ambient send site.
  7. `test_legacy_seam_values_are_accepted_shapes` — axis 2, ditto.
  8. `test_unguarded_reads_are_the_known_set`  — pins WHICH keys have no `has()` above them, so
     a guard silently disappearing upstream is visible here.

Absent peer source => FAIL, never skip, for the reason `test_wait_for_break_spelling.py` spells
out at length: a skip is indistinguishable from a deliberate one, and while the source is
unreadable every constant below is unchecked folklore.
"""
import ast
import difflib
import functools
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))  # tools/, for suite_paths
from suite_paths import SUITE_ROOT_ENV, suite_path  # noqa: E402

TOOLS = Path(__file__).resolve().parent
LEGACY_CPP = suite_path("oracle-old", "linux-port", "gui", "ControlSocket.cpp")


# ----------------------------------------------------------------------------------
# The value shapes each accessor actually honours, read off the accessor bodies.
#
# Row 3 re-derives the type branches from the source and fails if these stop matching.
# A "shape" here is a JSON shape, expressed as the Python value that serialises to it.
# ----------------------------------------------------------------------------------

# getBool's string arm is `return (s == "true" || s == "1" || s == "yes");` — note it returns
# FALSE for any other string rather than the default `d`, so a `getBool(k, true)` site reading
# `"on"` does not fall back to true, it reads false. That is why the three-element set matters.
GETBOOL_TRUE_STRINGS = ("true", "1", "yes")

SHAPES = {
    # accessor -> human description of what it honours (asserted structurally by row 3)
    "get": "JSON string, integer, float or boolean (array/object fall through to the default)",
    "getInt": "JSON number, or a string parseable as decimal / 0x-hex / $-hex "
              "(bool, array, object, empty and unparseable strings fall through to the default)",
    "getU32": "as getInt, truncated to 32 bits",
    "getBool": "JSON boolean, JSON number (!=0), or one of the strings "
               + "/".join(GETBOOL_TRUE_STRINGS),
}


# ----------------------------------------------------------------------------------
# THE PINNED CONTRACT — {method: {key: (accessor, default, guarded_by)}}
#
# Method names are CANONICAL (`read_memory`/`write_memory`, matching `CanonicalOp()` in the
# server and the wire names our tools send), not the internal Handlers() keys.
#
# `default`   — the value the accessor returns when the key is absent, unparseable, or the
#               wrong JSON type. Written as it appears in the C++ (an implicit default is
#               resolved from the accessor signature).
# `guarded_by`— None, or the shape of the `req.has(key)` guard that lexically encloses the read:
#               "block-if"     `if (req.has(k)) { ... }` / `else if (...)`
#               "same-line-if" `if (req.has(k)) x = req.getInt(k);`
#               "early-return" `if (!req.has(k)) return ErrorReply(...);` above the read
#               None means a MISSPELLED key reaches the default and the call still succeeds.
#
# Keys reached through a helper (`ResolveAddrDetailed` for addr/symbol, `ParseButtons` for
# buttons) are attributed to every method that calls the helper, which is where a client's
# mistake actually lands. A key read at several sites is unguarded here if ANY of those reads
# is unguarded — deliberately the conservative direction for a hazard inventory.
#
# DO NOT hand-edit. Regenerate by running this file; row 2 is the derivation.
# ----------------------------------------------------------------------------------
CONTRACT = {
    "audio_spectrum": {
        "fft_size": ("getU32", "4096", None),
        "max_hz": ("getU32", "0", None),
        "source": ("get", '"fm"', None),
    },
    "breakpoint_add": {
        "addr": ("get|getU32", '""|0', "block-if"),
        "symbol": ("get", '""', "block-if"),
    },
    "breakpoint_clear": {
        "addr": ("get|getU32", '""|0', "block-if"),
        "all": ("getBool", "false", None),
        "symbol": ("get", '""', "block-if"),
    },
    "call_stack": {
        "max_bytes": ("getInt", "256", None),
        "max_frames": ("getInt", "24", None),
    },
    "get_profiler_frames": {
        "frames": ("getInt", "0", "same-line-if"),
        "top": ("getInt", "0", "same-line-if"),
    },
    "hold": {
        "buttons": ("ParseButtons", "[]", "contains+is_array+is_string"),
        "down": ("getBool", "true", None),
    },
    "load_symbols": {
        "buildId": ("get", '""', None),
        "path": ("get", '""', None),
    },
    "log_tail": {
        "limit": ("getU32", "100", None),
        "since": ("getU32", "0", None),
    },
    "lookup_symbol": {
        "addr": ("getU32", "0", "block-if"),
        "name": ("get", '""', "block-if"),
    },
    "memory_hash": {
        "addr": ("get|getU32", '""|0', "block-if"),
        "len": ("getInt", "0", None),
        "symbol": ("get", '""', None),
    },
    "object_slot": {
        "slot": ("getInt", "0", None),
    },
    "press": {
        "buttons": ("ParseButtons", "[]", "contains+is_array+is_string"),
        "frames": ("getInt", "2", None),
    },
    "read_cram": {
        "line": ("getInt", "-1", None),
    },
    "read_memory": {
        "addr": ("get|getU32", '""|0', "block-if"),
        "len": ("getInt", "1", None),
        "symbol": ("get", '""', None),
    },
    "read_vram": {
        "addr": ("getU32", "0", None),
        "len": ("getInt", "32", None),
    },
    "reload_rom": {
        "path": ("get", '""', None),
        "reset": ("getBool", "true", None),
        "wait": ("getBool", "true", None),
    },
    "reset": {
        "run": ("getBool", "true", None),
    },
    "run_frames": {
        "frames": ("getInt", "1", None),
    },
    "run_to": {
        "addr": ("get|getU32", '""|0', "block-if"),
        "symbol": ("get", '""', "block-if"),
    },
    "run_to_scanline": {
        "line": ("getInt", "-1", None),
    },
    "screenshot": {
        "path": ("get", '""', None),
    },
    "set_channel_enabled": {
        "channel": ("get", '""', None),
        "enabled": ("getBool", "false", "early-return"),
    },
    "set_layer_enabled": {
        "enabled": ("getBool", "false", "early-return"),
        "layer": ("get", '""', None),
    },
    "set_profiler": {
        "enabled": ("getBool", "false", "early-return"),
    },
    "state_hash": {
        "includeFramebuffer": ("getBool", "false", None),
    },
    "step": {
        "count": ("getInt", "1", None),
    },
    "vgm_start": {
        "path": ("get", '""', None),
    },
    "wait_for_break": {
        "timeout_ms": ("getInt", "30000", None),
    },
    "watchpoint_add": {
        "addr": ("get|getU32", '""|0', "block-if"),
        "read": ("getBool", "false", None),
        "symbol": ("get", '""', "block-if"),
        "write": ("getBool", "true", None),
    },
    "write_cram": {
        "b": ("getInt", "-1", None),
        "g": ("getInt", "-1", None),
        "index": ("getInt", "-1", None),
        "line": ("getInt", "-1", None),
        "r": ("getInt", "-1", None),
        "raw": ("getU32", "0", "block-if"),
    },
    "write_memory": {
        "addr": ("get|getU32", '""|0', "block-if"),
        "bytes": ("get", '""', "block-if"),
        "symbol": ("get", '""', None),
        "value": ("getInt", "0", "block-if"),
        "width": ("getInt", "1", None),
    },
    "write_vram": {
        "addr": ("getU32", "0", None),
        "bytes": ("get", '""', "early-return"),
    },
    "z80_read": {
        "addr": ("getU32", "0", None),
        "len": ("getInt", "1", None),
    },
    "z80_write": {
        "addr": ("getU32", "0", None),
        "bytes": ("get", '""', "block-if"),
        "value": ("getInt", "0", "block-if"),
    },
}

# Methods the legacy server implements and that read NO parameters at all. Sending anything to
# these is silently ignored, but so is sending nothing, so they carry no key hazard. Derived
# (row 2) as `Handlers()` minus `CONTRACT`.
NO_PARAM_METHODS = {
    "debug_arbiter", "get_channel_states", "get_layer_states", "get_profiler", "log_clear",
    "breakpoint_list", "object_list", "pause", "ping", "player_state", "registers",
    "release_all", "resume",
    "status", "step_out", "step_over", "vgm_status", "vgm_stop", "z80_registers",
}

# ----------------------------------------------------------------------------------
# THE SILENT-DEFAULT INVENTORY — every (method, key) read with NO `req.has()` above it.
#
# On these, and only these, a MISSPELLED key is silent: the accessor returns its default and
# the handler replies ok. Everywhere else the misspelling hits a guard and comes back as an
# ErrorReply. Derived and compared by the last row; written out in full because it is the one
# thing in this file a reader wants to look up rather than compute.
#
# (The wrong VALUE TYPE is silent everywhere, guarded or not — `has()` returns true for any
# present non-null value. That hazard is the value row's, not this one's.)
# ----------------------------------------------------------------------------------
UNGUARDED_READS = {
    "audio_spectrum.fft_size", "audio_spectrum.max_hz", "audio_spectrum.source",
    "breakpoint_clear.all", "call_stack.max_bytes", "call_stack.max_frames", "hold.down",
    "load_symbols.buildId", "load_symbols.path", "log_tail.limit", "log_tail.since",
    "memory_hash.len", "memory_hash.symbol", "object_slot.slot", "press.frames",
    "read_cram.line", "read_memory.len", "read_memory.symbol", "read_vram.addr",
    "read_vram.len", "reload_rom.path", "reload_rom.reset", "reload_rom.wait", "reset.run",
    "run_frames.frames", "run_to_scanline.line", "screenshot.path",
    "set_channel_enabled.channel", "set_layer_enabled.layer", "state_hash.includeFramebuffer",
    "step.count", "vgm_start.path", "wait_for_break.timeout_ms", "watchpoint_add.read",
    "watchpoint_add.write", "write_cram.b", "write_cram.g", "write_cram.index",
    "write_cram.line", "write_cram.r", "write_memory.symbol", "write_memory.width",
    "write_vram.addr", "z80_read.addr", "z80_read.len", "z80_write.addr",
}

# The subset that names a MEMORY ADDRESS with no guard: misspell the key and the access lands
# at address zero. `read_memory`/`write_memory`/`run_to`/`breakpoint_add`/`watchpoint_add`/
# `memory_hash` are NOT here — their `addr` goes through `ResolveAddrDetailed`, which guards it.
UNGUARDED_MEMORY_ADDR = {"read_vram.addr", "write_vram.addr", "z80_read.addr", "z80_write.addr"}

# Population pins — row 4. Moving any of these means a parameter can now be read by a route
# rows 2 and 3 do not model, and the derivation must be re-done before the pin is re-typed.
ACCESSOR_CALL_COUNTS = {"get": 18, "getInt": 23, "getU32": 11, "getBool": 11}   # = 63
DIRECT_PARAM_READ_KEYS = 1      # ParseButtons' `buttons` — the 64th parameter
DIRECT_PARAM_READ_EXPRS = 2     # ...read through TWO `(*req.p)["buttons"]` expressions (:1579,:1580)
JSONOBJ_TAKING_FUNCTIONS = 58   # 57 taking it first + RunMethod taking it second
HANDLER_COUNT = 53

# ----------------------------------------------------------------------------------
# REGISTERED UNHONOURED KEYS
#
# A key our tools send to a legacy-seam method that the legacy server does not read. Each entry
# is (method, key) -> (exact site count, reason). The COUNT IS PINNED: an entry forgives the
# sites that exist, never the next one. An unregistered unhonoured key is a hard failure.
# ----------------------------------------------------------------------------------
UNHONOURED_KEYS_REGISTERED = {
    ("reset", "wait"): (
        12,
        "`OpReset` reads only `run`; it ALWAYS blocks on the main-thread drain (5 s deadline) "
        "when `ctx.pendingReset` is wired, so `wait` names behaviour that is unconditional and "
        "the server never looks at the key. Harmless as written (`wait: True` asks for what "
        "happens anyway) but it is a live instance of the silent-ignore class, and a future "
        "`wait: False` would read as a non-blocking reset and get a blocking one. The Rust core "
        "REFUSES the key (`emulator/reset` declares no properties, "
        "`unevaluatedProperties: false`), which is why the rust-seam sites all send `{}`. "
        "NOT fixed here: owner ruling Rider 3 — a legacy-seam probe's parameters change only in "
        "the commit that migrates it to the Rust core. Booked in docs/DEFERRED_WORK.md under "
        "F-LEGACY-SILENT-DEFAULT."),
}


# ----------------------------------------------------------------------------------
# Derivation from ControlSocket.cpp
# ----------------------------------------------------------------------------------

def _require_cpp() -> str:
    if not LEGACY_CPP.exists():
        pytest.fail(
            f"cannot derive the legacy seam contract: {LEGACY_CPP} is absent.\n\n"
            "This row FAILS rather than skipping, deliberately: while the peer source is "
            "unreadable, CONTRACT/SHAPES/the population pins above are unchecked folklore and "
            "every other row in this file is measuring our tools against a table nothing "
            "re-derived. A skip would render that as a deliberate choice.\n"
            f"Fix by restoring the peer checkout beside this one, or point {SUITE_ROOT_ENV} at "
            "the directory that holds them.")
    return LEGACY_CPP.read_text()


def _line_starts(text: str):
    starts = [0]
    for line in text.splitlines():
        starts.append(starts[-1] + len(line) + 1)
    return starts


def _lineno(starts, off: int) -> int:
    lo, hi = 0, len(starts) - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if starts[mid] <= off:
            lo = mid
        else:
            hi = mid - 1
    return lo + 1


def _block_end(text: str, start: int) -> int:
    """Index just past the block whose opening `{` is at or after `start`.

    Skips string literals, char literals and both comment forms so a brace inside any of them
    cannot unbalance the count.
    """
    i = text.index("{", start)
    depth, n = 0, len(text)
    while i < n:
        c = text[i]
        if c == '"':
            i += 1
            while i < n and text[i] != '"':
                i += 2 if text[i] == "\\" else 1
        elif c == "'":
            i += 1
            while i < n and text[i] != "'":
                i += 2 if text[i] == "\\" else 1
        elif c == "/" and i + 1 < n and text[i + 1] == "/":
            i = text.find("\n", i)
            if i < 0:
                return n
        elif c == "/" and i + 1 < n and text[i + 1] == "*":
            i = text.find("*/", i) + 1
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return n


_FN_RE = re.compile(
    r"^(?:static\s+)?[A-Za-z_][A-Za-z0-9_:<>,\s\*&]*?\b([A-Za-z_][A-Za-z0-9_]*)\s*\(\s*"
    r"const JsonObj\s*&", re.M)
_ACC_RE = re.compile(
    r'req\.(get|getInt|getU32|getBool)\(\s*"([A-Za-z_][A-Za-z0-9_]*)"\s*(?:,\s*([^)]*?))?\)')
_HAS_RE = re.compile(r'req\.has\(\s*"([A-Za-z_][A-Za-z0-9_]*)"\s*\)')

# The accessor signatures' own defaults, for reads that pass none.
_IMPLICIT_DEFAULT = {"get": '""', "getInt": "0", "getU32": "0", "getBool": "false"}


def _functions(src: str, starts):
    """name -> (first_line, last_line, body) for every function taking `const JsonObj&` first."""
    out = {}
    for m in _FN_RE.finditer(src):
        name = m.group(1)
        if name == "Handler":            # the `using Handler = ...(const JsonObj&, ...)` typedef
            continue
        end = _block_end(src, m.end())
        out[name] = (_lineno(starts, m.start()), _lineno(starts, end), src[m.start():end])
    return out


def _direct_reads(src: str, starts):
    """Parameter reads that bypass the accessor family entirely: `(*req.p)["key"]`."""
    return [(_lineno(starts, m.start()), m.group(1))
            for m in re.finditer(r'\(\*req\.p\)\["([A-Za-z_][A-Za-z0-9_]*)"\]', src)]


def _guards(src, starts, fn_start, fn_end, body, boff, lines):
    """Every `req.has(k)` guard in a function, as (key, kind, first_line, last_line)."""
    out = []
    for m in _HAS_RE.finditer(body):
        gline = _lineno(starts, boff + m.start())
        key = m.group(1)
        text = lines[gline - 1]
        negated = re.search(r'!\s*req\.has\(\s*"' + key + r'"', text) is not None
        if negated and "return" in text.split("req.has", 1)[1]:
            out.append((key, "early-return", gline, fn_end))
        elif not negated and re.search(r"\bif\s*\(\s*req\.has\(", text):
            tail = text[text.index("req.has"):]
            tail = tail[tail.index(")") + 1:].strip().lstrip(")").strip()
            if tail:                       # `if (req.has(k)) stmt;` — guards this line only
                out.append((key, "same-line-if", gline, gline))
            else:
                out.append((key, "block-if", gline,
                            _lineno(starts, _block_end(src, boff + m.end()))))
    return out


def derive():
    """Re-derive everything this file pins, straight out of `ControlSocket.cpp`.

    Returns (contract, no_param_methods, accessor_counts, direct_reads, fn_count, handlers).
    """
    src = _require_cpp()
    starts = _line_starts(src)
    lines = src.splitlines()
    fns = _functions(src, starts)

    hm = re.search(r"Handler>\s*h\s*=\s*\{(.*?)\n\s*\};", src, re.S)
    assert hm, "the Handlers() dispatch map is no longer recognisable in ControlSocket.cpp"
    handlers = dict(re.findall(r'\{\s*"([a-z_0-9]+)"\s*,\s*([A-Za-z_0-9]+)\s*\}', hm.group(1)))

    co = re.search(r"CanonicalOp\(const std::string& legacy\)\s*\{(.*?)\n\}", src, re.S)
    assert co, "CanonicalOp() is no longer recognisable — the wire method names cannot be derived"
    canonical = dict(re.findall(r'legacy\s*==\s*"([a-z_]+)"\s*\)\s*return\s*"([a-z_]+)"',
                                co.group(1)))

    handler_fns = set(handlers.values())
    helpers = [f for f in fns if f not in handler_fns]

    def reads(fn):
        fn_start, fn_end, body = fns[fn]
        boff = starts[fn_start - 1]
        gs = _guards(src, starts, fn_start, fn_end, body, boff, lines)
        out = []
        for m in _ACC_RE.finditer(body):
            ln = _lineno(starts, boff + m.start())
            acc, key = m.group(1), m.group(2)
            dflt = (m.group(3) or "").strip() or _IMPLICIT_DEFAULT[acc]
            g = next((kind for gk, kind, lo, hi in gs if gk == key and lo <= ln <= hi), None)
            out.append((key, acc, dflt, g))
        for ln, key in _direct_reads(body, _line_starts(body)):
            out.append((key, "ParseButtons", "[]", "contains+is_array+is_string"))
        return out

    def transitive(fn, seen=None):
        seen = seen if seen is not None else set()
        if fn in seen:
            return []
        seen.add(fn)
        out = list(reads(fn))
        for h in helpers:
            if h != fn and re.search(r"\b" + h + r"\s*\(", fns[fn][2]):
                out += transitive(h, seen)
        return out

    contract, no_param = {}, set()
    for op, fn in handlers.items():
        method = canonical.get(op, op)
        got = {}
        for key, acc, dflt, guard in transitive(fn):
            if key in got:
                pacc, pdflt, pguard = got[key]
                accs = pacc.split("|") + ([acc] if acc not in pacc.split("|") else [])
                dflts = pdflt.split("|") + ([dflt] if dflt not in pdflt.split("|") else [])
                # unguarded anywhere == unguarded, the conservative direction
                got[key] = ("|".join(accs), "|".join(dflts),
                            None if (pguard is None or guard is None) else pguard)
            else:
                got[key] = (acc, dflt, guard)
        if got:
            contract[method] = got
        else:
            no_param.add(method)

    counts = {a: len(re.findall(r"req\." + a + r'\("', src))
              for a in ("get", "getInt", "getU32", "getBool")}
    dr = _direct_reads(src, starts)
    return (contract, no_param, counts, (len(dr), len({k for _l, k in dr})),
            len(fns) + len(re.findall(r"[A-Za-z_]+\(const std::string& method, const JsonObj&",
                                      src)),
            handlers)


# ----------------------------------------------------------------------------------
# The client half: every legacy-seam send site in tools/
# ----------------------------------------------------------------------------------

def _imports(tree):
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            out.update(a.name for a in n.names)
        elif isinstance(n, ast.ImportFrom):
            out.add(n.module or "")
            out.update(f"{n.module}.{a.name}" for a in n.names)
    return out


def _own_seam(text: str, tree) -> str:
    """Seam evidence in THIS file alone. See `seam()` for the transitive resolution."""
    im = _imports(tree)
    if "aether_instance" in im or any(x.startswith("aether_instance.") for x in im):
        return "rust"
    if re.search(r'"oracle-aether"', text):
        return "rust"
    if "launcher" in im or any(x.endswith(".harness_path") for x in im):
        return "legacy"
    return "ambient"


def seam(text: str, tree, path=None, _seen=None) -> str:
    """Which emulator does this file dial?

    Read off IMPORTS and spawned binaries, never off prose. `test_wait_for_break_spelling.py`
    classifies by substring, which is right for the three files it looks at and wrong at this
    scale: `tick_variance_probe.py` says in a comment that `oracle-old/linux-port/harness` is
    "deliberately NOT importable from here", and a substring test reads that as legacy.

    `rust`    — imports `tools/aether_instance.py`, or spawns the `oracle-aether` binary itself.
    `legacy`  — imports `harness_path` / `launcher`, i.e. spawns the C++ `oracle_gui`.
    `ambient` — connects to a pre-existing socket. Treated as `legacy` below: BOTH servers
                default to `$XDG_RUNTIME_DIR/oracle.sock` so the path cannot discriminate, and
                the standing owner ruling pins the one such tool (`evict_witness.py`) to the
                legacy server its own docstring names.

    The evidence is FOLLOWED THROUGH LOCAL IMPORTS, because in this tree a probe routinely
    borrows its whole connection: `staging_lifetime_timeline.py` has no seam marker of its own
    and imports `Server` from `tick_variance_probe`, which spawns `oracle-aether`. Reading only
    its own text calls it ambient and then measures a Rust-seam probe against the C++ server's
    vocabulary. A file that imports both seams is a hard error rather than a guess.
    """
    _seen = _seen if _seen is not None else set()
    own = _own_seam(text, tree)
    if own != "ambient" or path is None:
        return own
    _seen.add(path.name)
    found = set()
    for name in sorted(_imports(tree)):
        mod = (TOOLS / (name.split(".")[0] + ".py"))
        if mod.name in _seen or not mod.exists():
            continue
        mtext = mod.read_text()
        found.add(seam(mtext, ast.parse(mtext, filename=str(mod)), mod, _seen))
    found.discard("ambient")
    if len(found) > 1:
        raise AssertionError(
            f"{path.name} imports modules that dial BOTH servers ({sorted(found)}); its seam "
            "cannot be resolved and the key/value rows would be measuring it against the wrong "
            "vocabulary. Split the import or give the file its own seam marker.")
    return found.pop() if found else "ambient"


# Calls that take a method NAME without sending it: a capability probe, not a request.
NON_SENDING_CALLEES = {"supports"}


def _method_arg_index(node: ast.Call):
    """Index of the `"emulator/<method>"` positional argument, or None.

    NOT hardcoded to 0. `b.call("emulator/read_memory", {...})` puts it first, but the retry
    wrapper `_c(b, "emulator/read_memory", {...}, 60.0)` puts it SECOND, and an extractor that
    only looked at `args[0]` silently measured zero send sites in `raster_frame_epoch_probe.py`
    — a legacy-seam probe with eight of them. `test_no_method_literal_escapes_the_extractor`
    below is the row that caught it and exists so it cannot happen again.
    """
    for i, a in enumerate(node.args):
        if isinstance(a, ast.Constant) and isinstance(a.value, str) \
                and a.value.startswith("emulator/"):
            return i
    return None


@functools.lru_cache(maxsize=1)
def _send_sites_cached():
    return tuple(_send_sites())


def send_sites():
    """Cached view of `_send_sites()` — the completeness row asks for it once per file."""
    return _send_sites_cached()


def _send_sites():
    """Every `emulator/<method>` send site in tools/, as
    (path, lineno, seam, method, [(key, value_ast_node)] or None for a non-literal params)."""
    for path in sorted(TOOLS.glob("*.py")):
        text = path.read_text()
        if '"emulator/' not in text:
            continue
        tree = ast.parse(text, filename=str(path))
        s = seam(text, tree, path)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fname = node.func.attr if isinstance(node.func, ast.Attribute) else (
                node.func.id if isinstance(node.func, ast.Name) else "")
            if fname in NON_SENDING_CALLEES:
                continue
            i = _method_arg_index(node)
            if i is None:
                continue
            a0 = node.args[i]
            method = a0.value.split("/", 1)[1]
            params = node.args[i + 1] if len(node.args) > i + 1 else next(
                (k.value for k in node.keywords if k.arg == "params"), None)
            if params is None:
                items = []
            elif isinstance(params, ast.Dict):
                items = list(zip(params.keys, params.values))
            else:
                items = None
            yield path, a0.lineno, s, method, items


# `read`/`write` are the server's INTERNAL handler keys; `CanonicalOp()` maps them to the wire
# names. A client may legitimately send either, so normalise before looking the method up.
_WIRE_ALIAS = {"read": "read_memory", "write": "write_memory"}


def _value_shape_ok(accessor: str, node) -> tuple[bool, str]:
    """(accepted, description). `accepted` is False ONLY for a value we can PROVE is wrong."""
    if isinstance(node, ast.Constant):
        v = node.value
        if accessor == "ParseButtons":
            return False, f"{v!r} (ParseButtons needs a JSON array of strings)"
        if accessor.startswith("getBool"):
            if isinstance(v, bool):
                return True, "bool"
            if isinstance(v, str):
                ok = v in GETBOOL_TRUE_STRINGS
                return ok, (f"{v!r} — getBool's string arm accepts only "
                            f"{'/'.join(GETBOOL_TRUE_STRINGS)}; anything else reads FALSE")
            if isinstance(v, (int, float)):
                return True, "number"
            return False, f"{v!r} (getBool honours bool, number, or 'true'/'1'/'yes')"
        if "getInt" in accessor or "getU32" in accessor:
            if isinstance(v, bool):
                return False, "a JSON boolean — getInt has NO is_boolean arm, it returns the default"
            if isinstance(v, (int, float)):
                return True, "number"
            if isinstance(v, str):
                s = v.strip()
                body = s[2:] if s[:2].lower() == "0x" else (s[1:] if s[:1] == "$" else s)
                base = 16 if s[:2].lower() == "0x" or s[:1] == "$" else 10
                try:
                    int(body, base)
                    return True, "parseable numeric string"
                except ValueError:
                    return False, (f"{v!r} — getInt's stoll throws and `catch (...)` returns "
                                   f"the default")
            return False, f"{v!r} (getInt honours numbers and numeric strings)"
        # plain `get`
        if isinstance(v, (str, int, float, bool)):
            return True, "scalar"
        return False, f"{v!r} (get falls through to the default for arrays and objects)"
    # Not a literal. `hex(x)` is the tree's overwhelmingly common addr form and is provably a
    # "0x..." string; anything else we cannot decide, and undecidable is not a failure.
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == "hex"):
        if "getInt" in accessor or "getU32" in accessor:
            return True, "hex() -> '0x...' string"
        if accessor.startswith("getBool"):
            return False, "hex() -> a '0x...' string, which getBool reads as FALSE"
    return True, "not statically decidable"


# ----------------------------------------------------------------------------------
# Rows
# ----------------------------------------------------------------------------------

def test_send_sites_are_found_at_all():
    """Guards the guard: a detector that silently matches nothing makes this whole file vacuous."""
    sites = list(send_sites())
    assert sites, "no `emulator/*` send site found in tools/ — the detector is broken, not the tree"
    seams = {s for _, _, s, _, _ in sites}
    assert {"legacy", "rust"} <= seams, (
        f"the seam classifier found only {sorted(seams)}; with no legacy-seam site the two "
        "hazard rows below assert nothing")
    non_rust = [s for s in sites if s[2] != "rust"]
    assert len(non_rust) >= 100, (
        f"only {len(non_rust)} non-rust send sites found — the classifier or the extractor "
        "regressed; this tree had 251 when the row was written")


# Syntactic positions in which an `emulator/<method>` literal is NOT a request, enumerated by
# node type so the exemption is structural rather than a list of blessed files:
#   Tuple/List — a capability roster iterated over (`for m in ("emulator/set_profiler", ...)`)
#   JoinedStr/BinOp — the method named inside a message
#   Compare/Subscript — `test_wait_for_break_spelling.py` reasoning ABOUT a method
#   Call:supports — a capability probe (also in NON_SENDING_CALLEES)
# Anything else — an assignment, a dict value, a return — means the method name travels in a
# VARIABLE, and a send through a variable is one this gate cannot read the keys of.
NON_SENDING_POSITIONS = (ast.Tuple, ast.List, ast.Set, ast.JoinedStr, ast.BinOp,
                         ast.Compare, ast.Subscript)


def test_no_method_literal_escapes_the_extractor():
    """COMPLETENESS. Account for EVERY `emulator/<method>` literal in tools/, one by one.

    A gate that enumerates the wrong population reports green about files it never opened. The
    first draft of `send_sites()` looked only at `args[0]` and therefore measured ZERO sites in
    `raster_frame_epoch_probe.py`, a legacy-seam probe that makes six of its calls through the
    `_c(bus, method, params, timeout)` wrapper — the method is its SECOND argument. Counting the
    literals independently of the call shape is what makes that visible instead of green.

    Every literal must be either extracted as a send site or sitting in one of
    `NON_SENDING_POSITIONS`. A literal anywhere else is a method name being handed to a
    variable, and this gate cannot follow it to the call that sends it.
    """
    by_file = {}
    for p, n, _s, m, _i in send_sites():
        by_file.setdefault(p.name, set()).add((n, m))
    missed = []
    for path in sorted(TOOLS.glob("*.py")):
        text = path.read_text()
        if '"emulator/' not in text:
            continue
        tree = ast.parse(text, filename=str(path))
        parent = {c: n for n in ast.walk(tree) for c in ast.iter_child_nodes(n)}
        extracted = by_file.get(path.name, set())
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Constant) and isinstance(node.value, str)
                    and node.value.startswith("emulator/")):
                continue
            if (node.lineno, node.value.split("/", 1)[1]) in extracted:
                continue
            par = parent.get(node)
            if isinstance(par, NON_SENDING_POSITIONS):
                continue
            fname = "" if not isinstance(par, ast.Call) else (
                par.func.attr if isinstance(par.func, ast.Attribute)
                else getattr(par.func, "id", ""))
            if isinstance(par, ast.Call) and fname in NON_SENDING_CALLEES:
                continue
            missed.append(f"{path.name}:{node.lineno} {node.value!r} sits in "
                          f"{type(par).__name__}"
                          + (f" (`{fname}(...)`)" if fname else "")
                          + " — neither an extracted send site nor a recognised non-sending "
                            "position")
    assert not missed, (
        f"{len(missed)} method literal(s) the extractor does not account for, so the key and "
        "value rows never see the request they end up in:\n  " + "\n  ".join(missed))


def test_contract_matches_the_legacy_server():
    """Re-derive CONTRACT and NO_PARAM_METHODS from ControlSocket.cpp and compare."""
    contract, no_param, _, _, _, handlers = derive()
    assert len(handlers) == HANDLER_COUNT, (
        f"the legacy server now dispatches {len(handlers)} methods, not {HANDLER_COUNT} — "
        "a new method may read parameters this file does not model")
    got = {m: {k: v for k, v in sorted(ks.items())} for m, ks in sorted(contract.items())}
    want = {m: {k: tuple(v) for k, v in sorted(ks.items())} for m, ks in sorted(CONTRACT.items())}
    if got != want:
        diffs = []
        for m in sorted(set(got) | set(want)):
            if m not in got:
                diffs.append(f"  {m}: pinned but the server no longer reads any key for it")
                continue
            if m not in want:
                diffs.append(f"  {m}: server reads {sorted(got[m])} but the pin has no entry")
                continue
            for k in sorted(set(got[m]) | set(want[m])):
                if got[m].get(k) != want[m].get(k):
                    diffs.append(f"  {m}.{k}: server says {got[m].get(k)}, pin says "
                                 f"{want[m].get(k)}")
        assert False, (
            f"{len(diffs)} row(s) of CONTRACT no longer match ControlSocket.cpp:\n"
            + "\n".join(diffs)
            + "\n\nRe-derive before re-typing the pin — the pin is what the two hazard rows "
              "measure our tools against, and an edited pin that was never derived is exactly "
              "the folklore this file exists to prevent.")
    assert no_param == NO_PARAM_METHODS, (
        f"the parameterless method set moved: +{sorted(no_param - NO_PARAM_METHODS)} "
        f"-{sorted(NO_PARAM_METHODS - no_param)}")


def test_accessor_value_semantics_are_unchanged():
    """SHAPES models the four accessors' branches; re-derive the branches from the struct body."""
    src = _require_cpp()
    struct = re.search(r"struct JsonObj\s*\{(.*?)\n\};", src, re.S)
    assert struct, "the JsonObj accessor struct is no longer recognisable in ControlSocket.cpp"
    body = struct.group(1)

    def arm(name):
        m = re.search(r"\b" + name + r"\(const std::string& k[^)]*\) const\s*\n?\s*\{", body)
        assert m, f"the {name}() accessor is gone from JsonObj"
        return body[m.end() - 1:_block_end(body, m.end() - 1)]

    has = arm("has")
    assert "contains(k)" in has and "is_null()" in has, (
        "has() no longer tests `contains && !is_null` — the whole 'present but wrong type "
        "passes the guard' argument in this file's docstring needs re-checking")

    for name in ("get", "getInt", "getU32", "getBool"):
        assert "if (!has(k)) return d;" in arm(name).replace("\n", " ") or name == "getU32", (
            f"{name}() no longer opens with the tolerant `if (!has(k)) return d;` — the silent "
            "default this file gates may be gone, or may have moved")

    g = arm("get")
    assert {"is_string", "is_number_integer", "is_number_unsigned", "is_number_float",
            "is_boolean"} == set(re.findall(r"is_[a-z_]+", g)) - {"is_null"}, (
        f"get()'s type arms changed to {sorted(set(re.findall(r'is_[a-z_]+', g)))}; SHAPES['get'] "
        "is now wrong")

    gi = arm("getInt")
    assert "catch (...)" in gi and "return d;" in gi, (
        "getInt no longer swallows an unparseable string — `addr: '0xZZZZ' -> 0` may be fixed")
    assert '"0x"' not in gi and "'x'" in gi and "'$'" in gi, (
        "getInt's hex-prefix handling changed; the numeric-string check in _value_shape_ok is "
        "now wrong")
    assert not re.search(r"is_boolean", gi), (
        "getInt gained an is_boolean arm — a JSON bool no longer silently reads as the default "
        "and _value_shape_ok must stop failing it")

    gb = arm("getBool")
    strings = tuple(re.findall(r's == "([a-z0-9]+)"', gb))
    assert strings == GETBOOL_TRUE_STRINGS, (
        f"getBool's accepted string set is now {strings}, not {GETBOOL_TRUE_STRINGS}")
    assert re.search(r'return \(s == "true".*\);', gb), (
        "getBool's string arm no longer RETURNS the comparison directly — check whether a "
        "non-matching string now falls back to `d` instead of reading false")


def test_parameter_read_population_is_closed():
    """63 accessor calls + 1 direct read = 64. A 65th means a new read mechanism appeared."""
    _, _, counts, direct, fn_count, _ = derive()
    assert counts == ACCESSOR_CALL_COUNTS, (
        f"the accessor family moved: {counts} vs pinned {ACCESSOR_CALL_COUNTS}")
    exprs, keys = direct
    assert (exprs, keys) == (DIRECT_PARAM_READ_EXPRS, DIRECT_PARAM_READ_KEYS), (
        f"{exprs} direct `(*req.p)[...]` expression(s) reading {keys} distinct key(s) in "
        f"ControlSocket.cpp, pinned {DIRECT_PARAM_READ_EXPRS}/{DIRECT_PARAM_READ_KEYS}. A "
        "parameter read outside the accessor family is invisible to the derivation unless it "
        "is one of the shapes _direct_reads() knows.")
    assert fn_count == JSONOBJ_TAKING_FUNCTIONS, (
        f"{fn_count} functions take a `const JsonObj&`, pinned {JSONOBJ_TAKING_FUNCTIONS} — a "
        "new helper may read parameters the per-handler inlining does not follow")
    total = sum(counts.values()) + keys
    assert total == 64, f"the parameter-read population is {total}, not the closed 64"


def test_legacy_seam_keys_are_honoured():
    """AXIS 1. Every key we send a legacy-seam method must be a key that method actually reads."""
    bad, registered_hits = [], {}
    for path, lineno, s, method, items in send_sites():
        if s == "rust" or items is None:
            continue
        m = _WIRE_ALIAS.get(method, method)
        if m not in CONTRACT:
            # Either parameterless (no key hazard) or not implemented at all — an unimplemented
            # method is answered with a JSON-RPC error, which is LOUD, and loud is not this
            # file's subject.
            continue
        for k, _ in items:
            if not (isinstance(k, ast.Constant) and isinstance(k.value, str)):
                continue
            if k.value in CONTRACT[m]:
                continue
            if (m, k.value) in UNHONOURED_KEYS_REGISTERED:
                registered_hits[(m, k.value)] = registered_hits.get((m, k.value), 0) + 1
                continue
            close = difflib.get_close_matches(k.value, sorted(CONTRACT[m]), n=1, cutoff=0.6)
            bad.append(f"{path.name}:{lineno} sends `{k.value}` to the {s}-seam "
                       f"`emulator/{method}`, which reads only {sorted(CONTRACT[m])}"
                       + (f" — did you mean `{close[0]}`?" if close else ""))
    assert not bad, (
        f"{len(bad)} legacy-seam send site(s) pass a key the server never reads. It does NOT "
        "error — the handler takes the accessor default and replies ok:\n  " + "\n  ".join(bad))

    for key, (want, reason) in UNHONOURED_KEYS_REGISTERED.items():
        got = registered_hits.get(key, 0)
        assert got == want, (
            f"registered unhonoured key {key[0]}.{key[1]} is now sent from {got} site(s), "
            f"pinned {want}. A registration forgives the sites that existed when it was "
            f"written, never the next one.\nReason on file: {reason}")


def test_legacy_seam_values_are_accepted_shapes():
    """AXIS 2. A correctly-spelled key with a shape the accessor does not honour is silent too."""
    bad = []
    for path, lineno, s, method, items in send_sites():
        if s == "rust" or items is None:
            continue
        m = _WIRE_ALIAS.get(method, method)
        if m not in CONTRACT:
            continue
        for k, v in items:
            if not (isinstance(k, ast.Constant) and isinstance(k.value, str)):
                continue
            spec = CONTRACT[m].get(k.value)
            if spec is None:
                continue                       # axis 1's problem, already reported there
            accessor, default, _guard = spec
            ok, why = _value_shape_ok(accessor, v)
            if not ok:
                bad.append(f"{path.name}:{lineno} `emulator/{method}` key `{k.value}` is read "
                           f"by {accessor} but is sent {why}; the server takes its default "
                           f"({default}) and replies ok")
    assert not bad, (
        f"{len(bad)} legacy-seam value(s) are a shape the accessor does not honour:\n  "
        + "\n  ".join(bad)
        + "\n\nThe key is spelled correctly, `has()` returns true, and the guard above it "
          "passes — only the accessor's own type arms reject it, silently.")


def test_unguarded_reads_are_the_known_set():
    """Which keys have NO `has()` above them — the ones where a misspelling is silent, not loud.

    Pinned as its own row because it is the difference between `write_vram`, where a misspelled
    `addr` writes VRAM at 0 and replies ok, and `write_memory`, where the same misspelling gets
    `ErrorReply("need addr or symbol")`. If a guard is ever removed upstream this row moves
    before anything else notices.
    """
    contract, _, _, _, _, _ = derive()
    got = {f"{m}.{k}" for m, ks in contract.items() for k, (_a, _d, g) in ks.items() if g is None}
    assert got == UNGUARDED_READS, (
        f"the unguarded-read inventory moved: newly unguarded "
        f"{sorted(got - UNGUARDED_READS)}, newly guarded {sorted(UNGUARDED_READS - got)}")

    # The subset that addresses machine memory with no guard above it. This is the set the
    # headline is actually true of: send `write_vram` with `addres` instead of `addr` and the
    # handler takes getU32's default of 0, writes your bytes to VRAM offset 0, and replies ok.
    #
    # ⚠ The wider F-LEGACY-SILENT-DEFAULT booking named `:348`, `:615`, `:739` and `:782` among
    # "six unguarded sites on memory paths". Re-derived here they are all GUARDED — `:348` by
    # `if (req.has("addr"))` in ResolveAddrDetailed, `:615`/`:739` by `else if (req.has("value"))`,
    # `:782` by `else if (req.has("addr"))` — so a misspelling at those four is LOUD
    # (`ErrorReply("need addr or symbol")` / `"need bytes or value"`). The two that ARE unguarded,
    # `:702` and `:726`, were correctly named; `read_vram`/`write_vram` (`:2110`, `:2140`) were
    # missed and are the same hazard. The type hazard is undiminished at all six:
    # `{"addr": "0xZZZZ"}` passes has(), throws in stoll, is swallowed by `catch (...)`, and
    # reads 0 — the guards only cover ABSENCE.
    memory = {r for r in got if r.split(".")[1] == "addr"}
    assert memory == UNGUARDED_MEMORY_ADDR, (
        f"the unguarded memory-path addr set is now {sorted(memory)}, not "
        f"{sorted(UNGUARDED_MEMORY_ADDR)}. These are the sites where a misspelled `addr` "
        "reaches getU32's default of 0 and the read/write lands at address zero with a "
        "success reply.")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
