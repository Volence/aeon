#!/usr/bin/env python3
"""build.sh's environment knobs, graded by EXECUTING the blocks build.sh runs.

  EMITTER   build.sh named the assembler's revision and recorded nothing about SIGIL_EMIT, so a
            split pair (sigil and emit_sound_blob from different revisions) was found by a peer
            rather than by any build's own output (docs/DEFERRED_WORK.md, the shared-emitter
            row, 2026-09-12). emit_sound_blob takes `--aeon` and `--out-dir` and nothing else
            (no `--version`), so its md5 is its identity; build.sh now prints it beside the
            `Assembler:` line.

HOW. Each block sits between `# >>> NAME` / `# <<< NAME` markers in build.sh, which say the
markers are load-bearing. The block is lifted and run under `bash -euo pipefail` (build.sh's
own `set` line) with a controlled environment. build.sh itself is NEVER invoked: a test in
build.sh's own pytest lane that calls build.sh against the real repo recurses (DEFERRED_WORK,
side findings of the 2026-09-11 lens-tools parcel, item (c)). Expected md5s are computed here
with hashlib from a file this test writes, never copied from a pin.

RUNNER: build.sh's pre-build tool-suite lane (`pytest tools -m "not needs_build"`), build-fatal.
Source only, no marker.
"""
import hashlib
import os
import subprocess
import tempfile

TOOLS = os.path.dirname(os.path.abspath(__file__))
BUILD_SH = os.path.join(os.path.dirname(TOOLS), "build.sh")


def _block(name):
    with open(BUILD_SH, "r", encoding="utf-8") as f:
        src = f.read()
    begin, end = "# >>> " + name, "# <<< " + name
    assert src.count(begin) == 1 and src.count(end) == 1, (
        "build.sh must carry exactly one %r / %r marker pair; this test lifts and runs the "
        "block between them" % (begin, end))
    i = src.index(begin) + len(begin)
    return src[i:src.index(end, i)]


def _run(script, args=(), **env_over):
    env = {k: v for k, v in os.environ.items()
           if k not in ("NO_LINT", "FAST", "SIGIL_EMIT", "SOUND_DRIVER_ENABLED")}
    env.update({k: v for k, v in env_over.items() if v is not None})
    p = subprocess.run(["bash", "-c", "set -euo pipefail\n" + script, "build.sh", *args],
                       env=env, capture_output=True, text=True, timeout=30)
    return p.returncode, p.stdout, p.stderr


# ------------------------------------------------------------------------ EMITTER
def test_the_emitter_md5_is_printed_when_sound_is_on():
    with tempfile.TemporaryDirectory() as d:
        emit = os.path.join(d, "emit_sound_blob")
        with open(emit, "wb") as f:
            f.write(b"not a real emitter, only bytes to hash\n")
        with open(emit, "rb") as f:
            want = hashlib.md5(f.read()).hexdigest()
        rc, out, err = _run(_block("EMITTER_IDENTITY"), SIGIL_EMIT=emit)
        assert rc == 0, (out, err)
        line = [l for l in out.splitlines() if l.startswith("Emitter:")]
        assert len(line) == 1, out
        assert want in line[0] and emit in line[0], (want, line[0])


def test_a_missing_emitter_is_named_not_hashed():
    for emit in (None, "", "/nonexistent/emit_sound_blob"):
        rc, out, err = _run(_block("EMITTER_IDENTITY"), SIGIL_EMIT=emit)
        assert rc == 0, (emit, out, err)
        assert "Emitter:" in out and "NOT FOUND" in out, (emit, out)


def test_a_silent_shape_says_the_emitter_is_not_used():
    rc, out, err = _run(_block("EMITTER_IDENTITY"), SOUND_DRIVER_ENABLED="0",
                        SIGIL_EMIT="/nonexistent/emit_sound_blob")
    assert rc == 0, (out, err)
    assert "Emitter:" in out and "not used" in out and "NOT FOUND" not in out, out
