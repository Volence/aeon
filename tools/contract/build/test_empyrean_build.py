"""Tests for the empyrean.build reference reader, against the contract vectors."""
import hashlib
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import empyrean_build as eb  # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))
# in empyrean the vectors are contract/schema/build/vectors; vendored (aeon tools/contract/build)
# they sit beside the reader. One test file, both layouts.
VEC = next(p for p in (os.path.join(_HERE, "vectors"),
                       os.path.join(_HERE, "..", "..", "contract", "schema", "build", "vectors"))
           if os.path.isdir(p))


def vec(kind, name):
    return os.path.join(VEC, kind, name + ".json")


def unwrapped(tmp_path, kind, name, mutate=None):
    """The vectors wrap the document as {why, doc}; the reader reads the bare doc."""
    with open(vec(kind, name)) as f:
        doc = json.load(f)["doc"]
    if mutate:
        mutate(doc)
    p = tmp_path / (name + ".build.json")
    p.write_text(json.dumps(doc))
    return str(p)


@pytest.mark.parametrize("name", sorted(
    n[:-5] for n in os.listdir(os.path.join(VEC, "pass"))))
def test_every_pass_vector_loads(tmp_path, name):
    b = eb.load(unwrapped(tmp_path, "pass", name), unbound=True)
    assert b.bound is False
    assert len(b.rom_sha256) == 64


def test_major_2_raises_unknown_major(tmp_path):
    with pytest.raises(eb.UnknownMajor) as e:
        eb.load(unwrapped(tmp_path, "red", "major-2"), unbound=True)
    assert e.value.found == 2


def test_major_checked_before_other_keys(tmp_path):
    def wreck(d):
        d["version"]["major"] = 2
        del d["rom"]
        d["symbols"] = "nonsense"
    with pytest.raises(eb.UnknownMajor):
        eb.load(unwrapped(tmp_path, "pass", "demo-minimal", wreck), unbound=True)


def test_unknown_format_refused_by_name(tmp_path):
    with pytest.raises(eb.UnknownFormat):
        eb.load(unwrapped(tmp_path, "red", "format-unknown"), unbound=True)


def test_other_red_vectors_fail_schema(tmp_path):
    for n in sorted(os.listdir(os.path.join(VEC, "red"))):
        n = n[:-5]
        if n in ("major-2", "format-unknown"):
            continue
        with pytest.raises(eb.InvalidBuild):
            eb.load(unwrapped(tmp_path, "red", n), unbound=True)


def test_minor_1_1_unknown_keys_load(tmp_path):
    b = eb.load(unwrapped(tmp_path, "pass", "minor-1-1-unknown-keys"), unbound=True)
    assert b.minor == 1


def test_binding_required_unless_unbound(tmp_path):
    p = unwrapped(tmp_path, "pass", "demo-minimal")
    with pytest.raises(eb.BindingRequired):
        eb.load(p)


def _bound(tmp_path, rom):
    def setsha(d):
        d["rom"]["sha256"] = hashlib.sha256(rom).hexdigest()
        d["rom"]["size"] = len(rom)
    return unwrapped(tmp_path, "pass", "demo-minimal", setsha)


def test_matching_rom_binds(tmp_path):
    rom = b"\x00" * 1024
    b = eb.load(_bound(tmp_path, rom), rom)
    assert b.bound is True


def test_one_byte_patched_rom_raises_not_bound(tmp_path):
    rom = bytes(1024)
    patched = bytearray(rom)
    patched[7] ^= 1
    with pytest.raises(eb.NotBound) as e:
        eb.load(_bound(tmp_path, rom), bytes(patched))
    assert e.value.expected == hashlib.sha256(rom).hexdigest()
    assert e.value.found == hashlib.sha256(bytes(patched)).hexdigest()
    assert len(e.value.expected) == 64 and len(e.value.found) == 64


def test_not_bound_compares_full_hash_not_prefix(tmp_path):
    rom = bytes(64)
    h = hashlib.sha256(rom).hexdigest()
    # same 16-digit prefix, different tail: must still be refused
    def setsha(d):
        d["rom"]["sha256"] = h[:16] + "0" * 48
    p = unwrapped(tmp_path, "pass", "demo-minimal", setsha)
    with pytest.raises(eb.NotBound):
        eb.load(p, rom)


@pytest.fixture
def banked(tmp_path):
    return eb.load(unwrapped(tmp_path, "pass", "z80-banked"), unbound=True)


def test_symbol_lookup(banked):
    s = banked.symbol("QueueDMA_Deferrable")
    assert s.vma == 7818 and s.kind == "proc"
    assert banked.symbol("ANIM_WALK").vma == 0
    assert banked.symbol("Z80_Driver_Entry", "z80").vma == 64
    with pytest.raises(KeyError):
        banked.symbol("QueueDMA_Deferrable", "z80")


def test_at_m68k_is_nearest_preceding(banked):
    r = banked.at("m68k", 7818 + 3)
    assert (r.symbol.name, r.disp, r.contains) == ("QueueDMA_Deferrable", 3, True)
    # past a label inside the proc: the label answers (the bus's rule), unsized
    r = banked.at("m68k", 7818 + 205)
    assert (r.symbol.name, r.disp, r.contains) == ("QueueDMA_Deferrable.full", 123, None)
    with pytest.raises(eb.SymbolNotFound):
        banked.at("m68k", 7817)


def test_banked_z80_uses_lma_bank(banked):
    # bank = lma >> 15: $28100 >> 15 == 5, $38100 >> 15 == 7
    assert banked.at("z80", 0x8100, bank=5).symbol.name == "Z80_BankedA"
    assert banked.at("z80", 0x8100, bank=7).symbol.name == "Z80_BankedB"
    with pytest.raises(eb.SymbolNotFound):
        banked.at("z80", 0x8100, bank=6)


def test_ambiguous_bank_without_bank(banked):
    with pytest.raises(eb.AmbiguousBank):
        banked.at("z80", 0x8100)
    with pytest.raises(eb.AmbiguousBank):
        banked.line_at("z80", 0x8100)


def test_z80_low_window_needs_no_bank(banked):
    assert banked.at("z80", 64).symbol.name == "Z80_Driver_Entry"


def test_line_at(banked):
    assert banked.line_at("m68k", 7818 + 3) == ("engine/dma_queue.emp", 42)
    assert banked.line_at("z80", 3) == ("generated/sound/driver.z80", 7)
    # a declared no-source range answers None, not a guess
    assert banked.line_at("m68k", 850200 + 4) is None
    assert banked.line_at("m68k", 99999999) is None


def test_line_at_banked_row(banked):
    # the z80 data row (vma 0x8100, lma 163968 -> bank 5), file index 2 line 0
    assert banked.line_at("z80", 0x8100, bank=5) == ("generated/sound/driver.z80", 0)
    assert banked.line_at("z80", 0x8100, bank=7) is None


def _cases():
    out = []
    for n in sorted(os.listdir(os.path.join(VEC, "lookup"))):
        with open(os.path.join(VEC, "lookup", n)) as f:
            v = json.load(f)
        for i, c in enumerate(v["cases"]):
            out.append(pytest.param(v["vector"], c, id=f"{n[:-5]}-{i}-{c['fn']}-{c['space']}-{c['addr']}"))
    return out


@pytest.mark.parametrize("vector,case", _cases())
def test_lookup_vectors(tmp_path, vector, case):
    """The shared reverse-lookup cases (vectors/lookup/): Oracle's reader runs the same file."""
    kind, name = vector[:-5].split("/")
    b = eb.load(unwrapped(tmp_path, kind, name), unbound=True)
    fn = getattr(b, case["fn"])
    want = case["expect"]
    if "error" in want:
        err = {"NotFound": eb.SymbolNotFound, "AmbiguousBank": eb.AmbiguousBank}[want["error"]]
        with pytest.raises(err):
            fn(case["space"], case["addr"], case.get("bank"))
        return
    got = fn(case["space"], case["addr"], case.get("bank"))
    if case["fn"] == "at":
        assert {"symbol": got.symbol.name, "disp": got.disp, "contains": got.contains} == want
    else:
        src = want["source"]
        assert got == (None if src is None else (src["file"], src["line"]))


def test_lookup_vectors_exist():
    assert len(_cases()) >= 20, "vectors/lookup holds too few cases: a parity gate with nothing to check"


@pytest.mark.parametrize("name", sorted(
    n[:-5] for n in os.listdir(os.path.join(VEC, "reader-red"))))
def test_every_reader_red_vector_is_refused(tmp_path, name):
    """Schema-valid documents that break a rule JSON Schema cannot state: every reader refuses them."""
    with open(vec("reader-red", name)) as f:
        assert json.load(f)["expect"]["reader"] == "InvalidBuild"
    with pytest.raises(eb.InvalidBuild):
        eb.load(unwrapped(tmp_path, "reader-red", name), unbound=True)


@pytest.mark.parametrize("major", [True, "1", -1, 1.0, 2.0, None])
def test_non_integer_major_is_invalid_not_unknown(tmp_path, major):
    def setmajor(d):
        d["version"]["major"] = major
    with pytest.raises(eb.InvalidBuild):
        eb.load(unwrapped(tmp_path, "pass", "demo-minimal", setmajor), unbound=True)


def test_layout_and_const(banked):
    assert banked.layout("Sst")["size"] == 80
    assert banked.const("MAX_RING_BUFFER") == 128
    with pytest.raises(KeyError):
        banked.layout("Nope")


def test_real_sidecar_if_present():
    p = os.environ.get("EMPYREAN_REAL_SIDECAR")
    if not p:
        pytest.skip("EMPYREAN_REAL_SIDECAR not set")
    rom_path = os.path.join(os.path.dirname(p), json.load(open(p))["rom"]["path"])
    with open(rom_path, "rb") as f:
        rom = f.read()
    b = eb.load(p, rom)
    assert b.bound


def test_missing_version_is_invalid_not_unknown_major(tmp_path):
    def drop(d):
        del d["version"]
    with pytest.raises(eb.InvalidBuild):
        eb.load(unwrapped(tmp_path, "pass", "demo-minimal", drop), unbound=True)

    def nomajor(d):
        d["version"] = {"minor": 0}
    with pytest.raises(eb.InvalidBuild):
        eb.load(unwrapped(tmp_path, "pass", "demo-minimal", nomajor), unbound=True)


def test_missing_schema_is_an_environment_fault(tmp_path, monkeypatch):
    monkeypatch.setenv("EMPYREAN_BUILD_SCHEMA", str(tmp_path / "nope.json"))
    monkeypatch.setattr(eb, "_find_schema_candidates", lambda: [str(tmp_path / "nope.json")])
    with pytest.raises(eb.SchemaMissing) as e:
        eb.load(unwrapped(tmp_path, "pass", "demo-minimal"), unbound=True)
    assert isinstance(e.value, eb.EnvironmentFault) and not isinstance(e.value, eb.InvalidBuild)


def test_missing_jsonschema_names_the_dependency(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "jsonschema", None)   # import raises ImportError
    with pytest.raises(eb.MissingDependency, match="jsonschema"):
        eb.load(unwrapped(tmp_path, "pass", "demo-minimal"), unbound=True)
