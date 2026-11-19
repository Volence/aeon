"""Reference reader for the `empyrean.build` export (G0a design 4.2, 4.3).

One `<stem>.build.json` per ROM. This module is the reference consumer: other
readers (Oracle's Rust one, Aurora, Seraph) must agree with it.

Order of checks in `load` (the schema cannot order its own errors, so the
reader does):
  1. the file is JSON and `format == "empyrean.build"`   -> UnknownFormat
  2. `version.major == 1`                                -> UnknownMajor(found)
     (no `version` / no `major` at all is InvalidBuild, not UnknownMajor(None))
  3. the schema (any minor >= 0; records are open)       -> InvalidBuild
  4. the binding: SHA-256 of the ROM bytes == rom.sha256 -> NotBound(expected, found)

Nothing but format and major is read before step 3. Binding compares the full
64-hex digest, never a prefix. `unbound=True` is the only way to skip step 4;
the object then reports `.bound == False`.

Z80 addresses in the banked window $8000-$FFFF are not unique across banks, so
`at` and `line_at` take a `bank` (= `lma >> 15`) there, and refuse to guess
without one (AmbiguousBank).
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
    if major != SUPPORTED_MAJOR or isinstance(major, bool):
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
        # per-space address tables: sorted by vma for containment search
        self._addr: dict = {}
        for s in self._syms:
            if s.space is not None:
                self._addr.setdefault(s.space, []).append(s)
        for v in self._addr.values():
            v.sort(key=lambda s: s.vma)
        self._max_size = {sp: max((s.size or 0) for s in v) for sp, v in self._addr.items()}
        self._addr_keys = {sp: [s.vma for s in v] for sp, v in self._addr.items()}
        self._rows: dict = {}
        for sec in doc["lines"]["sections"].values():
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

    def at(self, space: str, addr: int, bank: Optional[int] = None) -> Symbol:
        """The symbol covering `addr`: a sized symbol that contains it, else an exact-address one."""
        self._need_bank(space, addr, bank)
        want_bank = bank if (space == "z80" and in_window(addr)) else None
        syms = self._addr.get(space, [])
        keys = self._addr_keys.get(space, [])
        hi = bisect.bisect_right(keys, addr)
        exact = None
        reach = self._max_size.get(space, 0)
        for s in reversed(syms[:hi]):
            if s.vma + reach <= addr and exact is not None:
                break
            if want_bank is not None and s.bank != want_bank:
                continue
            if want_bank is None and s.bank is not None:
                continue
            if s.size is not None and s.vma <= addr < s.vma + s.size:
                return s
            if s.vma == addr and exact is None:
                exact = s
            if s.vma + reach <= addr:
                break
        if exact is not None:
            return exact
        raise SymbolNotFound(f"{space} ${addr:X}" + (f" bank {bank}" if bank is not None else ""))

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
