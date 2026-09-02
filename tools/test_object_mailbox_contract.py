"""Hold the live-object mailbox's PUBLISHED interface to the RAM and the code on disk.

WHAT THIS GATE EXISTS FOR
=========================
The `Obj_Req_*` cells (games/sonic4/config/ram.emp) are a published interface the moment
they land: an external tool resolves them by name out of the deb2 symbol table and writes
them by width and by offset. Three things have to agree, and NOTHING in the build can see
all three at once:

  1. the RAM declaration      games/sonic4/config/ram.emp   (names, widths, ORDER)
  2. the consumer's codes     games/sonic4/test/ojz_scroll_test.emp  (op + status consts)
  3. the published table      docs/ENGINE_ARCHITECTURE.md   "§4.12c"

sigil sees (1) and (2) and has no idea (3) exists. The doc is what the other lane builds
its spawn mode and object picker against, so a doc that drifts from the RAM is a client
writing the wrong offset with a green build on both sides -- and the client's failure mode
is a byte landing in the middle of a neighbouring field, which looks like an engine bug.

BOTH DIRECTIONS, DELIBERATELY (CODING_CONVENTIONS, "DOES THIS PARCEL MOVE A *NAME*?").
One direction asks *does the doc carry every declared cell* and catches a NEW cell missing
from the doc. The other asks *does the doc name anything that no longer exists* and catches
an OLD name gone dead. A rename passes a one-directional check silently, which is exactly
the case that slips furthest -- the field count never moves and every assertion still has
something to point at. Same pairing for the op/status codes.

THE ORDER IS CHECKED, NOT JUST THE SET. `Obj_Req_Flag` LAST is the protocol: the client
writes the payload and then the flag, and the consumer only reads the payload on a frame
where the flag is already nonzero. That is the entire concurrency control. A reorder that
put another cell after the flag would keep every name and width intact and quietly break
the lock-free property, so the declaration order is asserted against the doc's row order
and the flag's last position is asserted on its own.

AND THE SHAPE FENCE. The cells must sit inside the `if DEBUG == 1 @shape_divergent` group,
and `objreq_consume` must stay a `comptime fn ... -> Code` rather than becoming a `proc`.
Both are release-byte-identity mechanisms rather than style: a proc whose body is wholly
`if DEBUG == 1 {}` emits zero release BYTES but still declares a release LABEL, and that
label reaches convsym's deb2 appendix and moves every release CRC (measured on the
boot-override parcel: three parked zero-byte procs took s4.bin from d00dd11d/698411 to
84df688f/698409). A future "tidy this template into a proc" is a silent release change,
and nothing else in the tree would say so.

EVERY EXPECTATION IS DERIVED. There is no field name, width, offset or code VALUE typed
into an assertion in this file: both sides are parsed and compared to each other. The one
literal here is `Obj_Req_` itself, the prefix that identifies the group.

LOUD RATHER THAN GREEN WHEN IT CANNOT MEASURE. Every parse raises with the file and the
pattern it could not find. A gate that quietly parses zero cells and passes is the vacuity
this tree has been bitten by before, so `test_the_parsers_found_something` asserts a
non-empty parse for each of the three sources before any comparison runs.

PROVEN RED (2026-09-02), each arm firing alone, by editing the source on disk and
restoring from the committed baseline (`git checkout --` of the exact path), with
`__pycache__` cleared before every run:
  * rename `Obj_Req_Place` -> `Obj_Req_Placement` in ram.emp only
                                        -> test_ram_and_doc_declare_the_same_cells (both
                                           directions named in one message)
  * change `Obj_Req_Slot: u16` -> `u32` in ram.emp only
                                        -> test_ram_and_doc_agree_on_every_width
  * move `Obj_Req_Flag` above `Obj_Req_Status` in ram.emp only
                                        -> test_flag_is_the_last_cell
                                           and test_ram_and_doc_agree_on_order
  * change `OBJREQ_ERR_FULL = 3` -> `= 6` in ojz_scroll_test.emp only
                                        -> test_status_codes_match_the_doc
  * change `OBJREQ_OP_DELETE = 3` -> `= 4` in ojz_scroll_test.emp only
                                        -> test_op_codes_match_the_doc
  * `comptime fn objreq_consume()` -> `proc objreq_consume()`
                                        -> test_the_consumer_is_a_template_not_a_proc
  * move the `Obj_Req_*` cells out of the `if DEBUG == 1 @shape_divergent` group
                                        -> test_the_cells_are_debug_shape_only

RUN BY: `python3 -m pytest tools -q` -- the sweep build.sh runs build-fatally before every
canonical build (build.sh, "pytest tools" lane).
"""

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
RAM = REPO / "games/sonic4/config/ram.emp"
CONSUMER = REPO / "games/sonic4/test/ojz_scroll_test.emp"
ARCH = REPO / "docs/ENGINE_ARCHITECTURE.md"

PREFIX = "Obj_Req_"


def _read(path):
    if not path.is_file():
        raise AssertionError(f"{path} does not exist -- this gate cannot measure anything")
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------- source (1): ram.emp

def _debug_group_body(text):
    """The body of the LAST `if DEBUG == 1 @shape_divergent {` group in ram.emp.

    Brace-matched rather than regex-terminated, so a nested block inside the group cannot
    truncate the span. The group is located by its opening line; the mailbox lives in the
    game-RAM tail group beside the warp cells.
    """
    opens = [m for m in re.finditer(r"if\s+DEBUG\s*==\s*1\s*@shape_divergent\s*\{", text)]
    if not opens:
        raise AssertionError(
            f"{RAM}: found no `if DEBUG == 1 @shape_divergent {{` group -- the shape fence "
            "this gate checks against has moved or been renamed"
        )
    start = opens[-1].end()
    depth = 1
    i = start
    while i < len(text) and depth:
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
        i += 1
    if depth:
        raise AssertionError(f"{RAM}: unbalanced braces after the @shape_divergent group")
    return text[start : i - 1]


_RAM_FIELD = re.compile(r"^\s*(" + PREFIX + r"\w+)\s*:\s*(u8|u16|u32)\s*,", re.M)


def ram_cells(text=None):
    """[(name, width_str)] in DECLARATION order, from inside the shape-divergent group."""
    body = _debug_group_body(text if text is not None else _read(RAM))
    return [(m.group(1), m.group(2)) for m in _RAM_FIELD.finditer(body)]


def ram_cells_anywhere(text=None):
    """[(name, width)] from the WHOLE file -- used only to prove the shape fence."""
    src = text if text is not None else _read(RAM)
    return [(m.group(1), m.group(2)) for m in _RAM_FIELD.finditer(src)]


# ------------------------------------------------- source (2): ojz_scroll_test.emp

_CONST = re.compile(r"^const\s+(OBJREQ_\w+)\s*=\s*(\$?[0-9A-Fa-f]+)\s*(?://.*)?$", re.M)


def _num(tok):
    return int(tok[1:], 16) if tok.startswith("$") else int(tok, 10)


def consumer_consts():
    src = _read(CONSUMER)
    out = {m.group(1): _num(m.group(2)) for m in _CONST.finditer(src)}
    return out


def consumer_ops():
    return {k: v for k, v in consumer_consts().items() if k.startswith("OBJREQ_OP_")}


def consumer_statuses():
    c = consumer_consts()
    return {
        k: v
        for k, v in c.items()
        if k == "OBJREQ_OK" or k.startswith("OBJREQ_ERR_")
    }


# ------------------------------------------------ source (3): ENGINE_ARCHITECTURE.md

def _section_412c(text=None):
    src = text if text is not None else _read(ARCH)
    m = re.search(r"^#### 4\.12c .*$", src, re.M)
    if not m:
        raise AssertionError(
            f"{ARCH}: no `#### 4.12c` heading -- the published field list this gate holds "
            "the RAM against is gone or renumbered"
        )
    tail = src[m.end():]
    nxt = re.search(r"^#{2,4} ", tail, re.M)
    return tail[: nxt.start()] if nxt else tail


_DOC_FIELD = re.compile(r"^\|\s*`(" + PREFIX + r"\w+)`\s*\|\s*`(u8|u16|u32)`\s*\|", re.M)
# status rows: | `0` | OK | meaning |
_DOC_STATUS = re.compile(r"^\|\s*`(\d+)`\s*\|\s*([A-Z][A-Z ]*[A-Z]|OK)\s*\|", re.M)
# the op codes are published inside the Obj_Req_Op row's prose: `1` = SPAWN, ...
_DOC_OP = re.compile(r"`(\d+)`\s*=\s*(SPAWN|MOVE|DELETE)")


def doc_cells(text=None):
    return [(m.group(1), m.group(2)) for m in _DOC_FIELD.finditer(_section_412c(text))]


def doc_ops(text=None):
    sec = _section_412c(text)
    row = [ln for ln in sec.splitlines() if ln.startswith("| `" + PREFIX + "Op`")]
    if not row:
        raise AssertionError(f"{ARCH} 4.12c: no `{PREFIX}Op` row -- cannot read the op codes")
    return {name: int(num) for num, name in _DOC_OP.findall(row[0])}


def doc_statuses(text=None):
    return {
        int(m.group(1)): m.group(2).strip()
        for m in _DOC_STATUS.finditer(_section_412c(text))
    }


# --------------------------------------------------------------- name normalisation

def _op_key(const_name):
    """OBJREQ_OP_SPAWN -> SPAWN"""
    return const_name[len("OBJREQ_OP_"):]


def _status_key(const_name):
    """OBJREQ_OK -> OK; OBJREQ_ERR_POOL -> ... see the map below."""
    return "OK" if const_name == "OBJREQ_OK" else const_name[len("OBJREQ_ERR_"):]


# The doc spells status names as human phrases and the source as identifiers, so the two
# are joined on their VALUES and the names are reported only to make a failure readable.
# Nothing here asserts a spelling.


# ---------------------------------------------------------------------------- tests

def test_the_parsers_found_something():
    """Vacuity guard: a gate that parses zero of anything and passes is worse than absent."""
    assert ram_cells(), f"{RAM}: parsed no `{PREFIX}*` cells inside the shape-divergent group"
    assert doc_cells(), f"{ARCH} 4.12c: parsed no `{PREFIX}*` table rows"
    assert consumer_ops(), f"{CONSUMER}: parsed no `OBJREQ_OP_*` consts"
    assert consumer_statuses(), f"{CONSUMER}: parsed no status consts"
    assert doc_ops(), f"{ARCH} 4.12c: parsed no op codes out of the Obj_Req_Op row"
    assert doc_statuses(), f"{ARCH} 4.12c: parsed no status table rows"


def test_ram_and_doc_declare_the_same_cells():
    ram = {n for n, _ in ram_cells()}
    doc = {n for n, _ in doc_cells()}
    missing_from_doc = sorted(ram - doc)
    dead_in_doc = sorted(doc - ram)
    assert not missing_from_doc and not dead_in_doc, (
        f"the published field list and the RAM declaration disagree.\n"
        f"  declared in {RAM.name} but ABSENT from {ARCH.name} 4.12c: {missing_from_doc}\n"
        f"  named in {ARCH.name} 4.12c but NO LONGER declared: {dead_in_doc}\n"
        "Both directions are reported because a RENAME shows up as one of each -- "
        "fix the doc and the RAM together, they are one interface."
    )


def test_ram_and_doc_agree_on_every_width():
    ram = dict(ram_cells())
    doc = dict(doc_cells())
    bad = {n: (ram[n], doc[n]) for n in ram.keys() & doc.keys() if ram[n] != doc[n]}
    assert not bad, (
        "width drift between the RAM declaration and the published table "
        f"(cell: ram, doc): {bad}. A client writes by width; a doc that says u16 where the "
        "RAM says u32 makes it write half a field and clobber the next one."
    )


def test_ram_and_doc_agree_on_order():
    ram = [n for n, _ in ram_cells()]
    doc = [n for n, _ in doc_cells()]
    assert ram == doc, (
        f"cell ORDER differs.\n  {RAM.name}: {ram}\n  {ARCH.name} 4.12c: {doc}\n"
        "Order is the interface: offsets are derived from it, and the flag-last write "
        "order IS the concurrency control."
    )


def test_flag_is_the_last_cell():
    cells = [n for n, _ in ram_cells()]
    assert cells[-1] == PREFIX + "Flag", (
        f"{PREFIX}Flag must be the LAST mailbox cell declared; got {cells[-1]!r} after it "
        f"(order: {cells}). The protocol is 'write the payload, then the flag', and the "
        "consumer only reads the payload on a frame where the flag is already nonzero. A "
        "cell after the flag keeps every name and width intact and silently breaks that."
    )


def test_op_codes_match_the_doc():
    src = {_op_key(k): v for k, v in consumer_ops().items()}
    doc = doc_ops()
    assert src == doc, (
        f"op codes disagree.\n  {CONSUMER.name}: {src}\n  {ARCH.name} 4.12c: {doc}\n"
        "A client sending the doc's number reaches a different arm than the one it named."
    )


def test_status_codes_match_the_doc():
    src_values = sorted(consumer_statuses().values())
    doc_values = sorted(doc_statuses().keys())
    assert src_values == doc_values, (
        f"status code VALUES disagree.\n"
        f"  {CONSUMER.name}: { {k: v for k, v in sorted(consumer_statuses().items(), key=lambda kv: kv[1])} }\n"
        f"  {ARCH.name} 4.12c: {doc_statuses()}\n"
        "The doc is what a client switches on; an unpublished code reads as 'unknown "
        "failure' and a published one that the engine never writes reads as dead code."
    )


def test_status_zero_is_the_success_code():
    """Derived, not typed: whatever the source calls OK must be the doc's row 0."""
    ok = consumer_statuses()["OBJREQ_OK"]
    assert ok == 0, f"OBJREQ_OK is {ok}, not 0 -- a client tests `status == 0` for success"
    assert 0 in doc_statuses(), f"{ARCH.name} 4.12c publishes no status 0 row"


def test_the_cells_are_debug_shape_only():
    """Release-leak fence: every `Obj_Req_*` cell must sit inside the divergent group."""
    inside = {n for n, _ in ram_cells()}
    anywhere = {n for n, _ in ram_cells_anywhere()}
    leaked = sorted(anywhere - inside)
    assert not leaked, (
        f"{RAM}: these mailbox cells are declared OUTSIDE the "
        f"`if DEBUG == 1 @shape_divergent` group: {leaked}. They would then exist in the "
        "release shape, move every game RAM address below them, and put a DEBUG-only "
        "interface in the shipped ROM."
    )


def test_the_consumer_is_a_template_not_a_proc():
    src = _read(CONSUMER)
    assert re.search(r"^comptime fn objreq_consume\(\)\s*->\s*Code\b", src, re.M), (
        f"{CONSUMER}: `objreq_consume` is not a `comptime fn ... -> Code`. It MUST stay a "
        "template: a `proc` whose body is wholly inside `if DEBUG == 1 {}` emits zero "
        "release BYTES but still declares a release LABEL, that label reaches convsym's "
        "deb2 appendix, and the appendix moves every release CRC. Measured on the "
        "boot-override parcel: three parked zero-byte procs took s4.bin from "
        "d00dd11d/698411 to 84df688f/698409 -- identical through EndOfRom and still a "
        "changed ROM. Tidying this into a proc is a silent release-shape change."
    )
    assert not re.search(r"^\s*(pub\s+)?proc\s+objreq_consume\b", src, re.M), (
        f"{CONSUMER}: `objreq_consume` is declared as a proc -- see the message above."
    )


def test_the_op_and_status_codes_are_not_pub_consts():
    """They must not be harvested into link EquSyms, which reach release's deb2 appendix."""
    src = _read(CONSUMER)
    pubs = re.findall(r"^pub const\s+(OBJREQ_\w+)", src, re.M)
    assert not pubs, (
        f"{CONSUMER}: {pubs} are `pub const`. Game constants are re-exported as link "
        "EquSyms, and a link symbol feeds convsym's deb2 appendix in EVERY shape -- "
        "including release, where this whole feature is meant to be absent. Keep them "
        "module-local; docs/ENGINE_ARCHITECTURE.md 4.12c is their published home."
    )
    cfg = REPO / "games/sonic4/config/constants.emp"
    if cfg.is_file():
        stray = re.findall(r"^pub const\s+(OBJREQ_\w+)", cfg.read_text(encoding="utf-8"), re.M)
        assert not stray, (
            f"{cfg}: {stray} moved into the harvested game constants -- same reason."
        )


def test_every_cell_the_consumer_touches_is_declared():
    """A consumer reference to a cell the RAM does not declare would be a link extern."""
    declared = {n for n, _ in ram_cells()}
    used = set(re.findall(r"\b(" + PREFIX + r"\w+)\b", _read(CONSUMER)))
    # Names appear in prose comments too; that is fine -- the direction that matters is
    # that nothing referenced is undeclared.
    undeclared = sorted(used - declared)
    assert not undeclared, (
        f"{CONSUMER} names {undeclared}, which {RAM.name} does not declare inside the "
        "shape-divergent group."
    )
