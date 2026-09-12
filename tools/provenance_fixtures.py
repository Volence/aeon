"""Real Source Digest pairs for the provenance tests (LS-1a), built by the INSTALLED assembler.

Not a test module (no `test_` prefix): the helpers the provenance tests share. The fixtures
are real `sigil build` output, never hand-typed `DIGEST-` lines, so they cannot drift from
the emitter unnoticed: if sigil changes the section, these builds change with it.

PLAIN DEMO ONLY, and the reason is a measurement, not a preference: every file the plain
demo build reads is tracked (208 aeon-root READ rows, 0 untracked, 2026-09-12), so the
build works in a clean checkout. The DEBUG shapes also read `engine/debug/generated/*`,
which only build.sh's gen_compression_vectors step writes; a fresh worktree fails that
build (measured: `no module engine.compression_vectors found under the scan root`).
One plain demo assemble is ~0.75 s.

The build reads the aeon tree and writes ONLY under the directory it is given: build.sh's
own cross-game guard runs exactly this command, to a scratch path, on every sonic4 build.
"""

import os
import shutil
import subprocess

AEON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class NoAssembler(RuntimeError):
    """SIGIL_BUILD is unset or not executable. Callers FAIL on it, never skip: build.sh
    requires the assembler, and a skip would read "measured nothing" as a green dot."""


def sigil():
    exe = os.environ.get("SIGIL_BUILD")
    if not exe or not os.access(exe, os.X_OK):
        raise NoAssembler(
            "SIGIL_BUILD is unset or not executable, so no real Source Digest could be built "
            "and these provenance tests measured NOTHING. That is a failure, not a skip.")
    return exe


def build_demo(out_dir, rom_name="demo.bin", lst_name=None):
    """`sigil build` the plain demo into `out_dir`; returns (rom, lst) absolute paths.

    `rom_name` is the -o name, which is also the path DIGEST-ROM records; building the
    plain shape under a debug NAME is how a mis-shaped canonical artifact is made for real.
    """
    os.makedirs(out_dir, exist_ok=True)
    rom = os.path.join(os.path.abspath(out_dir), rom_name)
    lst = os.path.join(os.path.abspath(out_dir),
                       lst_name or os.path.splitext(rom_name)[0] + ".lst")
    p = subprocess.run([sigil(), "build", "--aeon", AEON, "--native", "--game", "demo",
                        "-o", rom, "--emit-lst", lst],
                       cwd=AEON, capture_output=True, text=True, timeout=600)
    if p.returncode != 0 or not os.path.isfile(lst):
        raise RuntimeError("the plain demo build failed (exit %d):\n%s"
                           % (p.returncode, (p.stdout + p.stderr)[-3000:]))
    return rom, lst


def aeon_rows(lst):
    """The aeon-root `DIGEST-READ` paths, parsed WITHOUT tools/artifact_provenance.py:
    the mirror must not be built by the code it is used to test."""
    out = []
    with open(lst, encoding="utf-8") as f:
        for line in f:
            if line.startswith("DIGEST-READ ") and " root=" not in line.split(" path=", 1)[0]:
                out.append(line.rstrip("\n").split(" path=", 1)[1])
    return out


def mirror(lst, dest):
    """Copy every aeon-root file `lst`'s build read into `dest`, at the same relative path.

    `dest` is then an aeon root the listing is fresh against (its module scan is exactly the
    read `.emp` rows, because sigil refuses a digest whose scan found a module it did not
    read), and it can be EDITED without touching the real tree. `root=sigil` rows still
    resolve against the real assembler's source root, read-only.
    """
    rows = aeon_rows(lst)
    for rel in rows:
        dst = os.path.join(dest, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(os.path.join(AEON, rel), dst)
    return rows


def rewrite(src, dst, edit):
    """Write `edit(text)` of listing `src` to `dst` (bytes preserved outside the edit)."""
    with open(src, encoding="utf-8", newline="") as f:
        text = f.read()
    new = edit(text)
    if new == text:
        raise AssertionError("the listing edit changed nothing; the fixture would test nothing")
    with open(dst, "w", encoding="utf-8", newline="") as f:
        f.write(new)
    return dst
