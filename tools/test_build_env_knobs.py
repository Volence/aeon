#!/usr/bin/env python3
"""build.sh's environment knobs, graded by EXECUTING the blocks build.sh runs.

  EMITTER   build.sh named the assembler's revision and recorded nothing about SIGIL_EMIT, so a
            split pair (sigil and emit_sound_blob from different revisions) was found by a peer
            rather than by any build's own output (docs/DEFERRED_WORK.md, the shared-emitter
            row, 2026-09-12). emit_sound_blob takes `--aeon` and `--out-dir` and nothing else
            (no `--version`), so its md5 is its identity; build.sh now prints it beside the
            `Assembler:` line.

  NO_LINT   An exported `NO_LINT=1` was IGNORED until 2026-09-12: build.sh set `NO_LINT=0`
            unconditionally before parsing flags, so only `-nl`/`--no-lint` (and FAST) skipped
            the lint lanes, while tools/landing_build.sh already refused an EXPORTED NO_LINT and
            CLAUDE.md, docs/OVERSEER-REFERENCE.md and several test docstrings named `NO_LINT=1`
            as an environment knob. Ruling (aeon overseer, 2026-09-12): honour the env var,
            default 0 when unset, and make the skip LOUD. The `-nl` path used to print nothing,
            so both routes now print a banner at the top AND a closing one at the bottom of the
            build. A value other than 0 or 1 is refused rather than guessed at.

HOW. Each block sits between `# >>> NAME` / `# <<< NAME` markers in build.sh, which say the
markers are load-bearing. The block is lifted and run under `bash -euo pipefail` (build.sh's
own `set` line) with a controlled environment. build.sh itself is NEVER invoked: a test in
build.sh's own pytest lane that calls build.sh against the real repo recurses (DEFERRED_WORK,
side findings of the 2026-09-11 lens-tools parcel, item (c)). Expected md5s are computed here
with hashlib from a file this test writes, never copied from a pin.

WHAT IT DOES NOT COVER: that the lanes build.sh guards with `NO_LINT` are the ones the banner
names. The banner lists them by hand; this file checks that the knob reaches NO_LINT and that
the skip is announced, not which `if` blocks read it.

RUNNER: build.sh's pre-build tool-suite lane (`pytest tools -m "not needs_build"`), build-fatal.
Source only, no marker. A NO_LINT=1 build skips that lane and so skips this file too;
tools/landing_build.sh refuses NO_LINT, so a landing run always reaches it.
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


# ------------------------------------------------------------------------ NO_LINT
def _no_lint(args=(), **env):
    return _run(_block("NO_LINT_KNOB") + '\necho "RESULT NO_LINT=${NO_LINT}"\n', args, **env)


def _result(out):
    lines = [l for l in out.splitlines() if l.startswith("RESULT NO_LINT=")]
    assert len(lines) == 1, out
    return lines[0].split("=", 1)[1]


def test_unset_means_the_lanes_run_and_nothing_is_announced():
    rc, out, err = _no_lint()
    assert rc == 0, (out, err)
    assert _result(out) == "0"
    assert "LINT LANES SKIPPED" not in out, out


def test_an_exported_NO_LINT_1_is_honoured_and_announced():
    rc, out, err = _no_lint(NO_LINT="1")
    assert rc == 0, (out, err)
    assert _result(out) == "1", "an exported NO_LINT=1 did not reach NO_LINT:\n" + out
    assert "LINT LANES SKIPPED" in out, out
    assert "NO_LINT=1 in the environment" in out, out
    for lane in ("pytest", "effects_budget_check", "emp_expect_fail"):
        assert lane in out, "the banner does not name the %s lane:\n%s" % (lane, out)


def test_the_flag_still_works_and_is_now_announced_too():
    for flag in ("-nl", "--no-lint"):
        rc, out, err = _no_lint(["sonic4", flag])
        assert rc == 0, (flag, out, err)
        assert _result(out) == "1", (flag, out)
        assert "LINT LANES SKIPPED" in out and flag in out, (flag, out)


def test_an_exported_NO_LINT_0_or_empty_runs_the_lanes():
    for v in ("0", ""):
        rc, out, err = _no_lint(NO_LINT=v)
        assert rc == 0, (v, out, err)
        assert _result(out) == "0", (v, out)
        assert "LINT LANES SKIPPED" not in out, (v, out)


def test_an_unrecognised_value_is_refused_not_guessed():
    for v in ("yes", "true", "2"):
        rc, out, err = _no_lint(NO_LINT=v)
        assert rc != 0, "NO_LINT=%s was accepted:\n%s" % (v, out)
        assert "RESULT" not in out, out
        assert "NO_LINT=%s" % v in out, out


def test_the_closing_banner_follows_the_request_and_nothing_else():
    """The closing banner reads NO_LINT_FROM, which only the knob block sets: FAST sets
    NO_LINT=1 on its own later and prints its own two banners."""
    tail = _block("NO_LINT_CLOSING")
    for env, args, want in (({"NO_LINT": "1"}, (), 2), ({}, ("sonic4", "-nl"), 2),
                            ({}, (), 0)):
        rc, out, err = _run(_block("NO_LINT_KNOB") + "\n" + tail, args, **env)
        assert rc == 0, (env, args, out, err)
        got = out.count("LINT LANES SKIPPED")
        assert got == want, (env, args, got, out)
    rc, out, err = _run('NO_LINT=1; NO_LINT_FROM=""\n' + tail)
    assert rc == 0 and "LINT LANES SKIPPED" not in out, (
        "the closing banner fired on NO_LINT alone (FAST's route), not on the request:\n" + out)


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
