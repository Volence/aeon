"""EFX-4b: every static raster program is emitted PADDED to the install copy's buffer.

`Raster_VBlank`'s `.copy_program` arm (engine/effects/raster.emp) copies a FIXED
RASTER_BUF_SIZE bytes from whatever static program was staged into `Raster_Buf_A`. Until
2026-09-11 static programs were declared `pub data X: [u16; raster_words(P)] =
raster_program(P)` -- sized to their content -- so a short one dragged the adjacent ROM into
the buffer past its terminator (lens EFX-4b). The fix pads every static program image to
the buffer, exactly as `patched_program` already pads a patched template, through
`static_program()` / `static_words()` in engine/effects/raster_dsl.emp. The two dense-tier
wire structs carry their own pad field and a `sizeof(..) == RASTER_BUF_SIZE` ensure in
raster.emp, so they need nothing here.

WHAT THIS LINT HOLDS, AND WHY IT IS A LINT. The unpadded spelling still COMPILES: it is the
spelling the docs taught for months, `raster_program()` stays public (every hand-twin pin and
`patched_program()` itself read its unpadded body), and a `Label` handed to `preset(raster:)`
carries no length a comptime guard could check. So the one thing that makes the old path
unauthorable is a refusal of the declaration shape itself: a `pub data` whose initializer
calls `raster_program(` directly. Such a declaration is only ever a static program -- a
patched template goes through `patched_program()` -- and nothing in the tree emits one for
any other reason.

IT CANNOT PASS ON AN EMPTY CORPUS. It also counts the `static_program(` declarations it
found, and fails if that is zero: a scan that stopped seeing the effects libraries would
otherwise report "no offenders" forever.
"""
import pathlib
import re

REPO = pathlib.Path(__file__).resolve().parent.parent
ROOTS = ("engine", "games")
# Poison modules are never lowered by a real entry and emit nothing; they build raster
# programs inside `ensure`s, never inside a `pub data`, but they are excluded by path rather
# than by that observation so a future poison spelling a `pub data` cannot trip this lint.
EXCLUDE = ("games/sonic4/test/poison/",)

PUB_DATA = re.compile(r"^\s*pub\s+data\s+(\w+)", re.M)
RAW = re.compile(r"\braster_program\s*\(")
PADDED = re.compile(r"\bstatic_program\s*\(")
OPEN, CLOSE = "([{", ")]}"


def _strip_comments(src: str) -> str:
    return "\n".join(line.split("//", 1)[0] for line in src.splitlines())


def _declaration(src: str, start: int) -> str:
    """The `pub data` item starting at `start`: through the first newline at which every
    bracket opened since `start` is closed again (a multi-line initializer stays whole)."""
    depth, i = 0, start
    while i < len(src):
        ch = src[i]
        if ch in OPEN:
            depth += 1
        elif ch in CLOSE:
            depth -= 1
        elif ch == "\n" and depth <= 0 and i > start:
            # a declaration whose `=` is still to come continues onto the next line
            if "=" in src[start:i]:
                return src[start:i]
        i += 1
    return src[start:]


def scan():
    offenders, padded, files = [], [], 0
    for root in ROOTS:
        for path in sorted((REPO / root).rglob("*.emp")):
            rel = path.relative_to(REPO).as_posix()
            if rel.startswith(EXCLUDE):
                continue
            files += 1
            src = _strip_comments(path.read_text())
            for m in PUB_DATA.finditer(src):
                decl = _declaration(src, m.start())
                if RAW.search(decl):
                    offenders.append(f"{rel}: pub data {m.group(1)}")
                if PADDED.search(decl):
                    padded.append(f"{rel}: pub data {m.group(1)}")
    return offenders, padded, files


def test_the_scan_sees_the_corpus():
    _, padded, files = scan()
    assert files > 0, f"found no .emp under {ROOTS} -- this lint measured nothing"
    assert padded, (
        "found no `pub data ... = static_program(..)` declaration anywhere under "
        f"{ROOTS}. Either the padded spelling was renamed (update PADDED in this file) or "
        "every static program was deleted; passing on zero would make the refusal below "
        "vacuous.")


def test_no_static_program_is_emitted_unpadded():
    offenders, _, _ = scan()
    assert not offenders, (
        "these `pub data` declarations emit a raster program through `raster_program(..)` "
        "directly, i.e. sized to its content:\n  " + "\n  ".join(offenders) + "\n\n"
        "Raster_VBlank's install copy reads a FIXED RASTER_BUF_SIZE bytes from a staged "
        "static program, so a short image drags whatever ROM follows it into Raster_Buf_A "
        "(lens EFX-4b). Spell it\n"
        "    pub data X: [u16; static_words(P)] = static_program(P)\n"
        "which pads the same words to the buffer, the way patched_program() pads a patched "
        "template. raster_program() stays the unpadded BODY for pins and for "
        "patched_program() itself.")
