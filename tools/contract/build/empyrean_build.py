"""Reference reader for the `empyrean.build` export (G0a design 4.2, 4.3).

One `<stem>.build.json` per ROM. This module is the reference consumer: other
readers (Oracle's Rust one, Aurora, Seraph) must agree with it on everything the
shared vectors pin: every pass vector loads, every reader-red vector is refused
(`vectors/reader-red/`), and every lookup case answers as written
(`vectors/lookup/`). Oracle's `build_export.rs` runs the same vectors.

Order of checks in `load` (the schema cannot order its own errors, so the
reader does):
  1. the file is JSON and `format == "empyrean.build"`   -> UnknownFormat
  2. `version.major == 1`                                -> UnknownMajor(found)
     (no `version` / no `major` at all, or a major that is not a non-negative
     JSON integer (`true`, `"1"`, `-1`, `1.0`), is InvalidBuild, not UnknownMajor)
  3. the schema (any minor >= 0; records are open)       -> InvalidBuild
     then the rules JSON Schema cannot state           -> InvalidBuild:
       - a z80 symbol or row in the window $8000-$FFFF has lma & $7FFF == vma & $7FFF
         (the window shows bank << 15 | (vma & $7FFF); any other lma is unreachable)
       - a code/data row's `file` index is inside `files`
  4. the binding: SHA-256 of the ROM bytes == rom.sha256 -> NotBound(expected, found)

Nothing but format and major is read before step 3. Binding compares the full
64-hex digest, never a prefix. `unbound=True` is the only way to skip step 4;
the object then reports `.bound == False`.

Z80 addresses in the banked window $8000-$FFFF are not unique across banks, so
`at` and `line_at` take a `bank` (= `lma >> 15`, the value the Z80 bank register
holds while those bytes are mapped) there, and refuse to guess without one
(AmbiguousBank), however many banks hold a symbol at the address.

Reverse lookup (`at`) is the bus's rule: the NEAREST PRECEDING symbol in the same
space (and, in the window, the same bank), with its displacement, and `contains`
saying whether the address is inside the symbol's size (None when unsized). It
names what a PC is in, so an address past a proc's end answers the proc (or the
label after it) with a displacement, never SymbolNotFound. Equates never answer.
"""
from __future__ import annotations

import bisect
import hashlib
import json
import os
from dataclasses import dataclass
from typing import Any, Optional

FORMAT = "empyrean.build"
SUPPORTED_MAJOR = 1
BANK_SHIFT = 15
WINDOW_LO, WINDOW_HI = 0x8000, 0xFFFF
_SCHEMA_NAME = "empyrean.build-1.schema.json"


class BuildError(Exception):
    pass


class UnknownFormat(BuildError):
    def __init__(self, found: Any):
        super().__init__(f"not an {FORMAT} file (format = {found!r})")
        self.found = found


class UnknownMajor(BuildError):
    def __init__(self, found: Any):
        super().__init__(f"unknown {FORMAT} major version {found!r}; this reader supports {SUPPORTED_MAJOR}")
        self.found = found


class InvalidBuild(BuildError):
    pass


class EnvironmentFault(BuildError):
    """The reader cannot run here (no schema file, no jsonschema): not a fault of the sidecar."""


class SchemaMissing(EnvironmentFault):
    pass


class MissingDependency(EnvironmentFault):
    pass


class BindingRequired(BuildError):
    pass


class NotBound(BuildError):
    def __init__(self, expected: str, found: str):
        super().__init__(f"ROM is not the one this export describes: export binds {expected}, ROM is {found}")
        self.expected = expected
        self.found = found


class AmbiguousBank(BuildError):
    pass


class SymbolNotFound(KeyError):
    pass


class AmbiguousName(BuildError):
    pass


@dataclass(frozen=True)
class Resolved:
    """A reverse-lookup answer: `symbol` is the nearest at or before the address, `disp` the bytes past
    it, `contains` whether `disp < symbol.size` (None for an unsized symbol)."""
    symbol: "Symbol"
    disp: int
    contains: Optional[bool]


@dataclass(frozen=True)
class Symbol:
    name: str
    vma: int
    kind: str
    public: bool
    space: Optional[str] = None
    lma: Optional[int] = None
    size: Optional[int] = None
    module: Optional[str] = None
    demangled: Optional[str] = None

    @property
    def bank(self) -> Optional[int]:
        """Bank of a banked-window z80 symbol, else None."""
        if self.space == "z80" and in_window(self.vma) and self.lma is not None:
            return self.lma >> BANK_SHIFT
        return None


def in_window(addr: int) -> bool:
    return WINDOW_LO <= addr <= WINDOW_HI


def _find_schema_candidates() -> list:
    here = os.path.dirname(os.path.abspath(__file__))
    env = os.environ.get("EMPYREAN_BUILD_SCHEMA")
    cands = [env] if env else []
    cands.append(os.path.join(here, "..", "..", "contract", "schema", "build", _SCHEMA_NAME))
    cands.append(os.path.join(here, _SCHEMA_NAME))
    return cands


def _find_schema() -> str:
    for c in _find_schema_candidates():
        if c and os.path.isfile(c):
            return c
    raise SchemaMissing(f"cannot find {_SCHEMA_NAME} beside the reader or in contract/schema/build "
                        "(set EMPYREAN_BUILD_SCHEMA): an environment fault, not a bad export")


def _validate(doc: dict) -> None:
    try:
        import jsonschema  # deferred so the format/major checks need nothing
    except ImportError as e:
        raise MissingDependency("the python package `jsonschema` (4.x) is required to validate "
                                "an empyrean.build file: pip install jsonschema") from e

    with open(_find_schema()) as f:
        schema = json.load(f)
    errs = sorted(jsonschema.Draft202012Validator(schema).iter_errors(doc),
                  key=lambda e: list(map(str, e.absolute_path)))
    if errs:
        e = errs[0]
        where = "/" + "/".join(map(str, e.absolute_path))
        raise InvalidBuild(f"{where}: {e.message}")


def sha256_hex(rom: bytes) -> str:
    return hashlib.sha256(rom).hexdigest()


def load(path: str, rom: "bytes | None" = None, *, unbound: bool = False) -> "BuildExport":
    with open(path, "rb") as f:
        try:
            doc = json.load(f)
        except ValueError as e:
            raise InvalidBuild(f"{path}: not JSON: {e}") from e
    if not isinstance(doc, dict) or doc.get("format") != FORMAT:
        raise UnknownFormat(doc.get("format") if isinstance(doc, dict) else None)
    version = doc.get("version")
    if not isinstance(version, dict) or "major" not in version:
        raise InvalidBuild("/version: missing or has no `major`")
    major = version["major"]
    if not isinstance(major, int) or isinstance(major, bool) or major < 0:
        raise InvalidBuild(f"/version/major: not a non-negative integer ({major!r})")
    if major != SUPPORTED_MAJOR:
        raise UnknownMajor(major)
    _validate(doc)
    bound = False
    if rom is not None:
        found = sha256_hex(rom)
        if found != doc["rom"]["sha256"]:
            raise NotBound(doc["rom"]["sha256"], found)
        bound = True
    elif not unbound:
        raise BindingRequired("pass the ROM bytes to bind against, or unbound=True to read without binding")
    return BuildExport(doc, bound)


class BuildExport:
    def __init__(self, doc: dict, bound: bool):
        self.doc = doc
        self.bound = bound
        self.minor: int = doc["version"]["minor"]
        self.rom_sha256: str = doc["rom"]["sha256"]
        self.rom_path: str = doc["rom"]["path"]
        self.files: list = doc["files"]
        self._syms = [_sym(r) for r in doc["symbols"]]
        self._by_name: dict = {}
        for s in self._syms:
            self._by_name.setdefault(s.name, []).append(s)
        self._layouts: dict = {}
        for r in doc["layouts"]:
            self._layouts.setdefault(r["name"], []).append(r)
        self._consts: dict = {}
        for r in doc["consts"]:
            self._consts.setdefault(r["name"], []).append(r)
        for i, s in enumerate(self._syms):
            if s.space == "z80" and in_window(s.vma):
                _window_rule(f"/symbols/{i}", "symbol", s.vma, s.lma)
        # Reverse lookup: three partitions, each with one sort key (Oracle's `Part`): m68k by vma,
        # Z80 RAM ($0000-$7FFF) by vma, the Z80 window by lma (the only unique address there).
        self._part: dict = {}
        for s in self._syms:
            if s.space is not None:
                self._part.setdefault(_part_of(s.space, s.vma), []).append(s)
        for p, v in self._part.items():
            v.sort(key=lambda s: (_sym_key(p, s), s.name))
        self._part_keys = {p: [_sym_key(p, s) for s in v] for p, v in self._part.items()}
        self._rows: dict = {}
        for name, sec in doc["lines"]["sections"].items():
            for j, r in enumerate(sec["rows"]):
                at = f"/lines/sections/{name}/rows/{j}"
                vma, lma, _ln, fi, _line, kind = r[:6]
                if sec["space"] == "z80" and in_window(vma):
                    _window_rule(at, "row", vma, lma)
                if kind in ("code", "data") and fi >= len(self.files):
                    raise InvalidBuild(f"{at}: file index {fi} is past the files table ({len(self.files)})")
            self._rows.setdefault(sec["space"], []).extend(sec["rows"])
        for v in self._rows.values():
            v.sort(key=lambda r: (r[0], r[1]))
        self._row_keys = {sp: [r[0] for r in v] for sp, v in self._rows.items()}

    # --- by name -----------------------------------------------------------
    def symbol(self, name: str, space: str = "m68k") -> Symbol:
        cands = self._by_name.get(name, [])
        hit = [s for s in cands if s.space == space] or [s for s in cands if s.space is None]
        if not hit:
            raise SymbolNotFound(f"{name} ({space})")
        if len(hit) > 1:
            raise AmbiguousName(f"{name} has {len(hit)} symbols in {space}")
        return hit[0]

    def layout(self, name: str) -> dict:
        return _one(self._layouts, name, "layout")

    def const(self, name: str) -> int:
        return _one(self._consts, name, "const")["value"]

    # --- by address --------------------------------------------------------
    @staticmethod
    def _need_bank(space: str, addr: int, bank: Optional[int]) -> None:
        if space == "z80" and in_window(addr) and bank is None:
            raise AmbiguousBank(
                f"z80 ${addr:04X} is in the banked window; the same address names a different byte in each bank. Pass bank (= lma >> {BANK_SHIFT}).")

    def at(self, space: str, addr: int, bank: Optional[int] = None) -> Resolved:
        """Reverse lookup, the bus's rule: the nearest symbol at or before `addr` in `space` (and, in the
        Z80 window, in `bank`), with the displacement past it. Several symbols at one address: the last
        in name order. A banked answer never borrows a symbol from another bank."""
        self._need_bank(space, addr, bank)
        part = _part_of(space, addr)
        key = ((bank << BANK_SHIFT) | (addr & 0x7FFF)) if part == "z80-window" else addr
        syms = self._part.get(part, [])
        hi = bisect.bisect_right(self._part_keys.get(part, []), key)
        miss = SymbolNotFound(f"{space} ${addr:X}" + (f" bank {bank}" if bank is not None else ""))
        if hi == 0:
            raise miss
        s = syms[hi - 1]
        skey = _sym_key(part, s)
        if part == "z80-window" and (skey >> BANK_SHIFT) != (key >> BANK_SHIFT):
            raise miss
        disp = key - skey
        return Resolved(s, disp, None if s.size is None else disp < s.size)

    def line_at(self, space: str, addr: int, bank: Optional[int] = None):
        """(`root/path`, line) of the source row covering `addr`; None for a no-source range or no row."""
        self._need_bank(space, addr, bank)
        want_bank = bank if (space == "z80" and in_window(addr)) else None
        rows = self._rows.get(space, [])
        hi = bisect.bisect_right(self._row_keys.get(space, []), addr)
        for r in reversed(rows[:hi]):
            vma, lma, ln, fi, line, kind = r[:6]
            if want_bank is not None and (lma >> BANK_SHIFT) != want_bank:
                continue
            if want_bank is None and space == "z80" and in_window(vma):
                continue
            if vma <= addr < vma + ln:
                if kind not in ("code", "data"):
                    return None
                f = self.files[fi]
                return (f"{f['root']}/{f['path']}", line)
            if addr - vma > 0x1000000:
                break
        return None


def _part_of(space: str, vma: int) -> str:
    if space == "z80":
        return "z80-window" if in_window(vma) else "z80-ram"
    return space


def _sym_key(part: str, s: Symbol) -> int:
    return s.lma if part == "z80-window" else s.vma


def _window_rule(at: str, what: str, vma: int, lma: Optional[int]) -> None:
    if lma is not None and (lma & 0x7FFF) != (vma & 0x7FFF):
        raise InvalidBuild(f"{at}: z80 window {what} at ${vma:04X} has lma ${lma:X}, which is not at that "
                           f"offset in any bank (lma & $7FFF must equal vma & $7FFF)")


def _sym(r: dict) -> Symbol:
    return Symbol(name=r["name"], vma=r["vma"], kind=r["kind"], public=r["public"],
                  space=r.get("space"), lma=r.get("lma"), size=r.get("size"),
                  module=r.get("module"), demangled=r.get("demangled"))


def _one(table: dict, name: str, what: str) -> dict:
    hit = table.get(name, [])
    if not hit:
        raise KeyError(f"{what} {name}")
    if len(hit) > 1:
        raise AmbiguousName(f"{what} {name} appears {len(hit)} times")
    return hit[0]
