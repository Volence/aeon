"""Scanline P2 — the shared reader for capability spans, in source and in listings.

ONE reader, three consumers: tools/test_scene_span_labels.py (source convention, in
the build.sh pytest lane), tools/demo_specialization_witness.py (the two-part demo
witness) and tools/effects_gates.py (the post-build differential span gates). They
must agree on what a span IS; two copies of this scan would be two things to keep in
step, which is the defect class this tree keeps paying for.

NOTHING HERE CARRIES A COPY OF THE CAPABILITY MASK. The bits come from
engine/level/scene_dsl.emp's `pub const CAP_*` declarations, the per-game masks from
each game's `SCANLINE_CAPS` binding, and the gated sites from the engine sources
themselves. An expectation copied from a nearby number is the recurring defect the
design doc names; every function below is a derivation instead.
"""

import os
import re

AEON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = os.path.join(AEON, "engine")
SCENE_DSL = os.path.join(ENGINE, "level", "scene_dsl.emp")

# `pub const CAP_PER_COL_VSRAM  = $0002` — declaration lines only. The reserved-bit
# COMMENT block beneath them (`CAP_FG_SPRITE_STRIPS=$0080, ...`) deliberately does
# not match: a reserved bit has no lowering, so a span named for one would bracket a
# block that cannot exist.
CAP_DECL_RE = re.compile(r"^pub const (CAP_[A-Z0-9_]+)\s*=\s*\$([0-9A-Fa-f]+)\s*$", re.M)

# `// RETIRED: CAP_PER_LINE=$0001 (2026-08-26, ...)` — a bit that HAD a lowering and lost
# it when its mechanism was deleted. It is not a declaration (no span may name it, no
# game may raise it) but it still occupies its bit: the allocation is one bit at a time
# from bit 0 and a retired bit is a HOLE, never re-used, so the gapless-run check in
# tools/test_scene_span_labels.py is over declared ∪ retired.
CAP_RETIRED_RE = re.compile(r"^// RETIRED: (CAP_[A-Z0-9_]+)=\$([0-9A-Fa-f]+)", re.M)

# The one spelling the engine uses for a capability gate.
GATE_RE = re.compile(r"if\s*\(\s*Game\.SCANLINE_CAPS\s*&\s*(CAP_[A-Z0-9_]+)\s*\)\s*!=\s*0\s*\{")

# `.cap_anchors_overlay_begin:` as authored in `.emp`.
LABEL_RE = re.compile(r"^\s*\.cap_([a-z0-9_]+)_(begin|end):", re.M)

# `    const SCANLINE_CAPS = $001F` inside a game's `implement Game { ... }`.
GAME_CAPS_RE = re.compile(r"^\s*const\s+SCANLINE_CAPS\s*=\s*(\$[0-9A-Fa-f]+|\d+)\s*$", re.M)

# A listing line naming a mangled local: `(0) 1039/76EE :   $engine.parallax$Proc$cap_x_begin:`
LST_SPAN_RE = re.compile(r"\$cap_([a-z0-9_]+)_(begin|end)\b")

# A listing line naming a TOP-LEVEL (unmangled) label — a section / proc head.
LST_HEAD_RE = re.compile(r"^\(\d+\) \d+/([0-9A-F]+) :\s+([A-Za-z_][A-Za-z0-9_]*):\s*$")


def capability_bits():
    """{CAP_NAME: bit} from scene_dsl.emp — the model's sole authority."""
    with open(SCENE_DSL, encoding="utf-8") as f:
        src = f.read()
    bits = {m.group(1): int(m.group(2), 16) for m in CAP_DECL_RE.finditer(src)}
    if not bits:
        raise SystemExit(
            "scene_spans: no `pub const CAP_*` declarations in %s — the capability "
            "authority moved or was re-spelled, and every derivation in this module "
            "reads it from here. Fix the parse; do not hard-code the bits." % SCENE_DSL)
    return bits


def retired_capability_bits():
    """{CAP_NAME: bit} for bits retired in scene_dsl.emp (see CAP_RETIRED_RE)."""
    with open(SCENE_DSL, encoding="utf-8") as f:
        src = f.read()
    return {m.group(1): int(m.group(2), 16) for m in CAP_RETIRED_RE.finditer(src)}


def game_caps(game):
    """A game's declared SCANLINE_CAPS, read from its own manifest."""
    path = os.path.join(AEON, "games", game, "config", "game.emp")
    with open(path, encoding="utf-8") as f:
        m = GAME_CAPS_RE.search(f.read())
    if not m:
        raise SystemExit(
            "scene_spans: no `const SCANLINE_CAPS` binding in %s — a game that does "
            "not declare the member cannot be specialised, and guessing zero here "
            "would silently assert the maximal elision." % path)
    v = m.group(1)
    return int(v[1:], 16) if v.startswith("$") else int(v)


def span_capability(span, bits):
    """Resolve `cap_<capability>_<site>` to its CAP_ name by LONGEST matching prefix.

    The site token exists because two labels of one name in a proc is a redefinition
    and several capabilities are gated at more than one site. Longest-prefix, not
    first-match, so a shorter capability name cannot shadow a longer one — a property
    test in test_scene_span_labels.py proves the declared set stays unambiguous.
    """
    lowered = {name[len("CAP_"):].lower(): name for name in bits}
    hits = [low for low in lowered if span == low or span.startswith(low + "_")]
    return lowered[max(hits, key=len)] if hits else None


def blank_comments_and_strings(src):
    """Replace comment and string bodies with spaces, preserving every offset.

    Required, not cosmetic: scene_dsl.emp DOCUMENTS the convention with a worked gate
    example in a comment, and a scan that read it would demand brackets around a block
    that does not exist. Strings go the same way so a `{name}` interpolation inside an
    `ensure` message cannot desync the brace counter.
    """
    out = list(src)
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        if c == "/" and i + 1 < n and src[i + 1] == "/":
            while i < n and src[i] != "\n":
                out[i] = " "
                i += 1
        elif c == "/" and i + 1 < n and src[i + 1] == "*":
            while i < n and not (src[i] == "*" and i + 1 < n and src[i + 1] == "/"):
                if src[i] != "\n":
                    out[i] = " "
                i += 1
            for _ in range(2):
                if i < n:
                    out[i] = " "
                    i += 1
        elif c == '"':
            out[i] = " "
            i += 1
            while i < n and src[i] != '"':
                if src[i] == "\\" and i + 1 < n:
                    out[i] = " "
                    i += 1
                if src[i] != "\n":
                    out[i] = " "
                i += 1
            if i < n:
                out[i] = " "
                i += 1
        else:
            i += 1
    return "".join(out)


def emp_sources():
    for dirpath, dirnames, filenames in os.walk(ENGINE):
        dirnames[:] = [d for d in dirnames if d not in (".git", "generated")]
        for name in sorted(filenames):
            if name.endswith(".emp"):
                yield os.path.join(dirpath, name)


def block_end(src, open_brace):
    """Index of the `}` closing the brace at `open_brace` (comment/string-neutralised)."""
    depth = 0
    i = open_brace
    while i < len(src):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise AssertionError("unbalanced braces after offset %d" % open_brace)


def gated_blocks():
    """(path, CAP_NAME, start, end) per gate; start/end bound the `{...}` body."""
    out = []
    for path in emp_sources():
        with open(path, encoding="utf-8") as f:
            src = blank_comments_and_strings(f.read())
        for m in GATE_RE.finditer(src):
            brace = src.index("{", m.start())
            out.append((path, m.group(1), brace, block_end(src, brace)))
    return out


def brackets():
    """(path, span, kind, offset) per bracketing label in the engine sources."""
    out = []
    for path in emp_sources():
        with open(path, encoding="utf-8") as f:
            src = blank_comments_and_strings(f.read())
        for m in LABEL_RE.finditer(src):
            out.append((path, m.group(1), m.group(2), m.start()))
    return out


def expected_spans(caps):
    """The span names a build with mask `caps` MUST emit — derived, never listed.

    A span survives iff its own capability bit is raised AND every gate ENCLOSING it
    is raised too: `cap_multi_deform_table_band` sits inside the CAP_DEFORM sampling
    gate, so a game raising CAP_MULTI_DEFORM_TABLE but not CAP_DEFORM emits neither.
    Getting that wrong in either direction turns the differential gate into a hand list
    with extra steps.
    """
    bits = capability_bits()
    blocks = gated_blocks()
    out = set()
    for path, span, kind, off in brackets():
        own = span_capability(span, bits)
        if own is None:
            continue
        enclosing = [c for p, c, s, e in blocks if p == path and s < off < e]
        if all(caps & bits[c] for c in enclosing) and caps & bits[own]:
            out.add(span)
    return out


def lst_span_kinds(path):
    """{span: {"begin", "end"}} — which BOUNDARY symbols a listing actually carries.

    Kept separate from `lst_spans` because a HALF-present span is its own failure and
    an early version of the differential was blind to it: renaming one `_begin` in a
    listing left the `_end` naming the same span, the set-level comparison saw no
    change, and the poison passed. A span gate that cannot tell one boundary from two
    cannot measure a region.
    """
    out = {}
    with open(path, encoding="utf-8", errors="replace") as f:
        for m in LST_SPAN_RE.finditer(f.read()):
            out.setdefault(m.group(1), set()).add(m.group(2))
    return out


def lst_spans(path):
    """Span names with ANY boundary symbol present in a listing.

    "Any", not "both", on purpose: for the demo-absence half a stray half-bracket is
    still a leak. Pairing is checked separately, by the caller, through
    `lst_span_kinds`.
    """
    return set(lst_span_kinds(path))


def lst_unpaired_spans(path):
    """Spans whose listing carries only one of the two boundary symbols."""
    return sorted(s for s, k in lst_span_kinds(path).items() if k != {"begin", "end"})


def lst_proc_sizes(path):
    """{proc: bytes} from a listing, sized head-to-next-head in address order.

    ROM LENGTH IS NOT CODE SIZE — placer fill absorbs an elision between anchored
    sections, so a gate reading `ls -la` measures the placer. This measures the
    listing instead. The size of a head includes any inter-proc alignment padding
    before the next head, so a ±small delta on a proc nobody touched is a gap moving,
    not code; callers that care compare NAMED procs, and the caller in
    demo_specialization_witness compares the same proc across two FIXTURES rather
    than across two builds, where the padding rule is identical on both sides.
    """
    heads = {}
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = LST_HEAD_RE.match(line.rstrip("\n"))
            if m:
                heads.setdefault(m.group(2), int(m.group(1), 16))
    rom = sorted(((a, n) for n, a in heads.items() if a < 0x800000))
    return {n: (rom[i + 1][0] - a if i + 1 < len(rom) else 0)
            for i, (a, n) in enumerate(rom)}


def source_spans_by_cap():
    """{CAP_NAME: {span, ...}} — every bracketed span in the ENGINE SOURCES, per bit.

    The source-side complement of `expected_spans` (P3 Task 16). `expected_spans`
    answers "what must a build with THIS mask emit"; this answers "which bits have a
    lowering AT ALL". The difference matters exactly when no fixture raises a bit:
    a bit that is gated in source but raised by neither shipped game (adoption
    pending, PARK-1) is a different state from a `pub const` bit with no brackets
    anywhere (a lowering deleted out from under its bit, or a bit promoted ahead of
    its subject — the vacuous-gate shape). tools/effects_gates.py's scanline_spans
    lane reports the two differently, and this is the derivation it reads.
    """
    bits = capability_bits()
    out = {}
    for _path, span, _kind, _off in brackets():
        cap = span_capability(span, bits)
        if cap:
            out.setdefault(cap, set()).add(span)
    return out


def gated_procs():
    """{proc_name: {CAP_NAME, ...}} — every proc that hosts a bracketed span.

    Read from the SOURCE (the `proc <Name> (` header enclosing each bracket), so the
    witness does not have to be told which procs specialise.
    """
    bits = capability_bits()
    proc_re = re.compile(r"^\s*(?:pub\s+)?proc\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", re.M)
    out = {}
    for path in emp_sources():
        with open(path, encoding="utf-8") as f:
            src = blank_comments_and_strings(f.read())
        heads = [(m.start(), m.group(1)) for m in proc_re.finditer(src)]
        if not heads:
            continue
        for m in LABEL_RE.finditer(src):
            owner = None
            for start, name in heads:
                if start < m.start():
                    owner = name
                else:
                    break
            if owner:
                cap = span_capability(m.group(1), bits)
                if cap:
                    out.setdefault(owner, set()).add(cap)
    return out
