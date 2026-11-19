"""Drift gate for the vendored empyrean.build contract (tools/contract/build/, G0a).

The reader, its tests, the build schema and the vectors are vendored from empyrean and pinned by
`SOURCE` (the empyrean commit, a sha256 per file). Two checks, both loud:

  * ALWAYS: every vendored file hashes to its SOURCE line, and no unlisted file sits in the
    directory (a hand edit, or a file added without re-vendoring, fails here).
  * When the sibling empyrean checkout resolves AND holds a file: the vendored bytes must equal the
    upstream bytes. A file the checkout does not hold yet (empyrean's branch not merged) is NOT a
    pass: it is reported as a warning naming it, and only its SOURCE hash is checked.

Fix drift by changing empyrean first, then `python3 tools/vendor_contract_build.py`."""
import hashlib
import warnings
from pathlib import Path

import pytest

import suite_paths
import vendor_contract_build as vcb

DEST = vcb.DEST


def _pinned() -> dict:
    out, in_files = {}, False
    for ln in (DEST / "SOURCE").read_text().splitlines():
        if ln.strip() == "files:":
            in_files = True
        elif in_files and ln.strip():
            h, rel = ln.split("  ", 1)
            out[rel] = h
    return out


def _vendored_files() -> set:
    return {p.relative_to(DEST).as_posix() for p in DEST.rglob("*")
            if p.is_file() and p.name != "SOURCE" and "__pycache__" not in p.parts
            and p.suffix != ".pyc"}


def test_source_pins_every_vendored_file_and_only_those():
    pinned = _pinned()
    assert pinned, "SOURCE lists no files"
    assert set(pinned) == _vendored_files(), (
        "SOURCE and tools/contract/build disagree: "
        f"unpinned {sorted(_vendored_files() - set(pinned))}, missing {sorted(set(pinned) - _vendored_files())}")
    for rel, h in sorted(pinned.items()):
        got = hashlib.sha256((DEST / rel).read_bytes()).hexdigest()
        assert got == h, f"VENDOR DRIFT: {rel} is {got} but SOURCE pins {h} (hand-edited? re-vendor from empyrean)"


def _upstream():
    try:
        return suite_paths.empyrean_dir()
    except suite_paths.CheckoutNotFound:
        return None


def test_vendored_bytes_equal_the_upstream_checkout():
    up = _upstream()
    if up is None:
        warnings.warn("no empyrean checkout resolves: vendored files checked against SOURCE only")
        return
    absent, drift = [], []
    for rel in sorted(_pinned()):
        f = up / vcb.upstream_of(rel)
        if not f.is_file():
            absent.append(rel)
        elif f.read_bytes() != (DEST / rel).read_bytes():
            drift.append(rel)
    if absent:
        warnings.warn(f"{len(absent)} vendored file(s) are not in {up} yet (empyrean branch unmerged?); "
                      f"SOURCE hashes only for: {absent[:3]}{'...' if len(absent) > 3 else ''}")
    assert not drift, (f"VENDOR DRIFT against {up}: {drift}. Upstream moved or the copy was edited: "
                       "change empyrean first, then python3 tools/vendor_contract_build.py")


def test_the_leg_tools_import_the_vendored_reader():
    import leg_provenance  # noqa: F401  (puts the vendored reader on sys.path)
    import empyrean_build
    assert Path(empyrean_build.__file__).resolve().parent == DEST.resolve()
