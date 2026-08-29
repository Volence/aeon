"""Glide_Collide must resolve the odd 'no usable angle' sentinel — S3K parity.

WHAT THIS PROTECTS
------------------
`Collision_ProbeDown` returns the AngleTable byte verbatim; its own docstring in
`games/sonic4/player/player_sensors.emp` says so ("raw angle (odd flag passes
through)"). An ODD byte in that table is not an angle: it is the "no usable
angle" sentinel. Every floor consumer in this engine reaches the surface through
`Player_SensorFloor`, which tests `btst #0, d1` before the value is ever used as
a direction — every consumer except `Glide_Collide`, which called the probe core
directly and wrote the raw byte into `angle(a0)`. That made the glide the sole
site in the engine able to install an odd angle, and `Air_Collide` states the
opposite as an invariant in a comment beside code that depends on it:

    "airborne angle decay: 2/frame toward 0 ... Angles here are always even
     (the odd-flag sensors substitute cardinals), so +/-2 lands exactly on 0"

From an odd angle that loop is a period-2 cycle ($FF -> $01 -> $FF -> ...) that
never terminates. Diagnosed in docs/GLIDE_LANDING_ANGLE_DIAGNOSIS.md section 6
as a prediction; measured here as a property of the SHIPPED collision tables,
where attr $01 — the S&K shape-255 full block that is the bulk floor of OJZ
act 1 — carries angle $FF.

S3K DOES apply this substitution, at this point, in this path. The citations are
re-derived from the donor at test time (see `s3k_check_floor_tail`), not copied.

WHAT IS DELIBERATELY *NOT* CHECKED
----------------------------------
The divergence rule (|angle - surface| >= $20 -> cardinal) that
`Player_SensorFloor` ALSO applies. S3K has no such rule on any airborne landing
path; it lives only in the grounded per-frame update `Player_Angle`. Requiring it
here would reroute every glide landing on a genuine >= 45-degree slope to
PSTATE_SLIDE, which is a behaviour ruling. Booked in docs/DEFERRED_WORK.md.

NOTHING BELOW IS A COPIED NUMBER. The sentinel test's shape comes from the
donor, the substituted cardinal comes from the donor, the decay step comes from
`player_air.emp`, the floor-class mask comes from `engine/system/constants.emp`,
and the population comes from the interned tables that reach the ROM.

HONESTY NOTE: this is a SOURCE + DATA gate, not a runtime one. It proves the
instructions are in the source and that no angle the shipped tables can supply
to a glide landing breaks the decay invariant. It does not run the ROM. The
runtime confirmations are TAG-2 and TAG-3 in the diagnosis document.
"""

import os
import re

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))

GLIDE_EMP = os.path.join(ROOT, "games", "sonic4", "player", "player_glide.emp")
AIR_EMP = os.path.join(ROOT, "games", "sonic4", "player", "player_air.emp")
SENSORS_EMP = os.path.join(ROOT, "games", "sonic4", "player", "player_sensors.emp")
KNUCKLES_EMP = os.path.join(ROOT, "games", "sonic4", "player", "knuckles.emp")
CONSTANTS_EMP = os.path.join(ROOT, "engine", "system", "constants.emp")
COLLISION_DIR = os.path.join(ROOT, "games", "sonic4", "data", "collision")

# A worktree checkout sits under .claude/worktrees/, where ../../skdisasm
# resolves wrong — honour the same override the collision importers honour.
SK_ASM = os.path.join(
    os.environ.get("AEON_SKDISASM_DIR",
                   os.path.normpath(os.path.join(ROOT, "..", "skdisasm"))),
    "sonic3k.asm")


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _int(tok):
    tok = tok.strip()
    return int(tok[1:], 16) if tok.startswith("$") else int(tok, 10)


def _code_lines(text):
    """Strip `//` and `;` comments; drop blanks."""
    out = []
    for raw in text.splitlines():
        line = raw.split("//", 1)[0]
        line = re.sub(r"(?<!')\s;.*$", "", line)
        line = line.strip()
        if line:
            out.append(line)
    return out


def _read(path, what):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError as exc:
        pytest.fail(f"cannot read {path} ({what}): {exc}")


def _emp_const(path, name):
    src = _read(path, f"const {name}")
    m = re.search(rf"^\s*(?:pub\s+)?const\s+{re.escape(name)}\s*=\s*"
                  r"(\$[0-9A-Fa-f]+|\d+)\s*(?://.*)?$", src, re.M)
    assert m, (
        f"could not find `const {name} = ...` in {path}. This test DERIVES its "
        f"constants from the engine source and will not fall back to a literal.")
    return _int(m.group(1))


# --------------------------------------------------------------------------
# fixtures — the two sources of truth
# --------------------------------------------------------------------------

@pytest.fixture(scope="module")
def s3k_check_floor_tail():
    """S3K's `Sonic_CheckFloor` tail — the resolution S3K applies on a landing.

    Returns (angle_reg, zero_reg). Loud if the donor no longer has the shape,
    because then this test's expectation has no source and must not be assumed.
    """
    src = _read(SK_ASM, "S3K donor")
    m = re.search(r"^Sonic_CheckFloor:\s*$(.*?)^; End of function Sonic_CheckFloor",
                  src, re.M | re.S)
    assert m, (
        "Sonic_CheckFloor not found in the S3K donor. This test derives its "
        "expectation from the donor; point AEON_SKDISASM_DIR at skdisasm.")
    body = m.group(1)

    # the tail: btst #0,dX / beq / move.b dY,dX  — the odd-flag substitution
    tail = re.search(
        r"btst\s+#0,\s*(d\d)\s*\n\s*beq(?:\.[sw])?\s+\S+\s*\n\s*move\.b\s+(d\d),\s*\1",
        body)
    assert tail, (
        "S3K's Sonic_CheckFloor no longer ends in the odd-flag substitution "
        "`btst #0,dX / beq / move.b dY,dX`. Re-derive the citation before "
        "trusting this gate.")
    angle_reg, zero_reg = tail.group(1), tail.group(2)

    # ... and the substituted value must be provably 0 in that same body
    assert re.search(rf"move\.b\s+#0,\s*{zero_reg}\b", body), (
        f"S3K substitutes {zero_reg} for an odd angle but this body never sets "
        f"{zero_reg} to 0 — the cardinal this gate expects is not derivable.")
    return angle_reg, zero_reg


@pytest.fixture(scope="module")
def glide_floor_land():
    """The Glide_Collide floor-land block: probe call -> `move.b dX, angle(a0)`."""
    src = _read(GLIDE_EMP, "Glide_Collide")
    m = re.search(r"^proc Glide_Collide\b.*?^\}", src, re.M | re.S)
    assert m, "proc Glide_Collide not found in player_glide.emp"
    lines = _code_lines(m.group(0))

    starts = [i for i, l in enumerate(lines) if "Collision_ProbeDown" in l]
    assert len(starts) == 1, (
        f"expected exactly one Collision_ProbeDown call in Glide_Collide, "
        f"found {len(starts)}: {[lines[i] for i in starts]}")
    ends = [i for i, l in enumerate(lines)
            if re.match(r"move\.b\s+d\d,\s*angle\(a0\)", l)]
    assert len(ends) == 1, (
        f"expected exactly one `move.b dN, angle(a0)` in Glide_Collide, "
        f"found {len(ends)}: {[lines[i] for i in ends]}")
    assert ends[0] > starts[0]
    return lines[starts[0]:ends[0] + 1]


@pytest.fixture(scope="module")
def air_decay_step():
    """`Air_Collide`'s airborne angle decay step, parsed from the source."""
    src = _read(AIR_EMP, "Air_Collide")
    m = re.search(r"^pub proc Air_Collide\b.*?^\}", src, re.M | re.S)
    assert m, "pub proc Air_Collide not found in player_air.emp"
    lines = _code_lines(m.group(0))
    # the decay is the first addq/subq pair on d0 after `move.b angle(a0), d0`
    try:
        head = next(i for i, l in enumerate(lines)
                    if re.match(r"move\.b\s+angle\(a0\),\s*d0", l))
    except StopIteration:
        pytest.fail("Air_Collide no longer opens its decay with "
                    "`move.b angle(a0), d0` — re-derive this gate.")
    window = lines[head:head + 12]
    up = re.search(r"addq\.b\s+#(\d+),\s*d0", "\n".join(window))
    dn = re.search(r"subq\.b\s+#(\d+),\s*d0", "\n".join(window))
    assert up and dn, (
        "Air_Collide's angle decay is no longer an addq/subq pair on d0 — "
        "the termination model below no longer describes it.")
    assert int(up.group(1)) == int(dn.group(1)), (
        "Air_Collide's decay is asymmetric; the termination model assumes one "
        "step magnitude.")
    return int(up.group(1))


@pytest.fixture(scope="module")
def floor_installable_angles():
    """Every angle byte a FLOOR probe can supply, from the interned tables.

    Derivation (player_sensors.emp `probe_core`, `.cell`): the class gate is
    `SolidityTable[attr] & d6`, and Glide_Collide passes `d6 = SOLID_TOP`. So an
    attr can supply an angle to a glide landing exactly when
    `solidity[attr] & SOLID_TOP` is nonzero.
    """
    solid_top = _emp_const(CONSTANTS_EMP, "SOLID_TOP")
    try:
        with open(os.path.join(COLLISION_DIR, "angles.bin"), "rb") as f:
            angles = f.read()
        with open(os.path.join(COLLISION_DIR, "solidity.bin"), "rb") as f:
            solidity = f.read()
    except OSError as exc:
        pytest.fail(f"cannot read the interned collision tables: {exc}")
    assert len(angles) == len(solidity) == 256, (
        f"interned tables are {len(angles)}/{len(solidity)} bytes, expected "
        f"256 each — the derivation below indexes them by attr byte.")
    return {i: angles[i] for i in range(256) if solidity[i] & solid_top}


# --------------------------------------------------------------------------
# 1. the fix is present, and its shape is the donor's
# --------------------------------------------------------------------------

def test_glide_landing_resolves_the_odd_sentinel(glide_floor_land,
                                                 s3k_check_floor_tail):
    """Glide_Collide substitutes the down cardinal for an odd probe angle."""
    _, _ = s3k_check_floor_tail            # donor shape re-derived (loud if gone)
    block = "\n".join(glide_floor_land)

    m = re.search(
        r"btst\s+#0,\s*(d\d)\b.*?\n\s*beq\s+(\S+).*?\n\s*moveq\s+#(\$?[0-9A-Fa-f]+),\s*\1\b",
        block, re.S)
    assert m, (
        "Glide_Collide does not resolve the odd 'no usable angle' sentinel "
        "between its Collision_ProbeDown call and its write to angle(a0).\n"
        "Collision_ProbeDown returns the AngleTable byte RAW; an odd byte is "
        "the sentinel, not an angle. S3K's own glide floor land "
        "(Knux_DoLevelCollision_CheckRet -> sub_11FD6 -> Sonic_CheckFloor) "
        "substitutes the down cardinal for it.\nBlock was:\n" + block)

    reg = m.group(1)
    assert _int(m.group(3)) == 0, (
        f"the sentinel substitute is {m.group(3)}, but S3K's Sonic_CheckFloor "
        f"substitutes 0 (its d2 is `move.b #0,d2`), and this probe is fixed-DOWN "
        f"so quadrant 0's cardinal is $00.")

    written = re.search(r"move\.b\s+(d\d),\s*angle\(a0\)", block)
    assert written and written.group(1) == reg, (
        f"the resolution is applied to {reg} but angle(a0) is written from "
        f"{written.group(1) if written else '?'} — the substitution does not "
        f"reach the field it is supposed to protect.")


def test_probe_core_still_returns_a_raw_angle():
    """The premise: the probe core is documented and coded as RAW.

    If this ever stops being true the test above is guarding a no-op, so it is
    asserted rather than assumed.
    """
    src = _read(SENSORS_EMP, "probe_core")
    assert re.search(r"raw angle \(odd flag passes through\)", src), (
        "player_sensors.emp no longer documents the probe core's angle as raw "
        "with the odd flag passing through. Re-derive this gate: if the core "
        "resolves the sentinel itself, the glide's substitution is dead code.")


# --------------------------------------------------------------------------
# 2. the behavioural consequence, over the bytes that reach the ROM
# --------------------------------------------------------------------------

def test_shipped_tables_contain_the_sentinel(floor_installable_angles):
    """VACUITY REFUSAL — the population must actually contain the hazard.

    A green result on a table with no odd-angled floor attr would prove nothing.
    """
    assert floor_installable_angles, (
        "no attr in the interned tables passes the floor class — this gate has "
        "no population and refuses to pass vacuously.")
    odd = {a: v for a, v in floor_installable_angles.items() if v & 1}
    assert odd, (
        "no floor-class attr in the shipped tables carries an odd angle byte. "
        "That is possible but suspicious: S&K's own full-solid block (shape "
        "255) has angle $FF, and it is the bulk floor of most zones. If this "
        "fires, confirm the collision tables were regenerated correctly before "
        "relaxing it.")


def test_airborne_decay_terminates_from_every_installed_angle(
        air_decay_step, floor_installable_angles, glide_floor_land):
    """The invariant Air_Collide's own comment states, checked end to end.

    Model: what a glide landing installs (the resolved probe angle), fed into
    Air_Collide's decay loop. Both halves are parsed from the tree.
    """
    block = "\n".join(glide_floor_land)
    resolves = bool(re.search(r"btst\s+#0,\s*d\d", block))

    step = air_decay_step
    bad = []
    for attr, raw in sorted(floor_installable_angles.items()):
        installed = 0 if (resolves and (raw & 1)) else raw
        # Air_Collide: beq done / bpl -> subq / else addq, all byte-wide
        a = installed
        for _ in range(256):
            if a == 0:
                break
            a = (a - step) & 0xFF if a < 0x80 else (a + step) & 0xFF
        else:
            bad.append((attr, raw, installed))

    assert not bad, (
        "Air_Collide's airborne angle decay never reaches 0 from an angle a "
        "glide landing can install. Its own comment states the opposite as an "
        "invariant (\"Angles here are always even ... so +/-2 lands exactly on "
        "0\"); with an odd angle installed the loop is a period-2 cycle that "
        "runs for the whole airborne period, and the landing divergence guard "
        "is then measured from +/-1 instead of 0.\n"
        "attr / raw table angle / installed: "
        + ", ".join(f"${a:02X} / ${r:02X} / ${i:02X}" for a, r, i in bad))


# --------------------------------------------------------------------------
# 3. scope — this change cannot reach Sonic or Tails
# --------------------------------------------------------------------------

def test_glide_collide_is_knuckles_only():
    """Backs the scope claim with a check instead of a sentence."""
    glide_src = _read(GLIDE_EMP, "glide module")
    callers = set()
    for m in re.finditer(r"^(pub\s+)?proc\s+(\w+)\b.*?^\}", glide_src, re.M | re.S):
        # code lines only — a prose mention of the routine is not a call site
        body = "\n".join(_code_lines(m.group(0)))
        if re.search(r"\bjbsr\s+Glide_Collide\b", body) and m.group(2) != "Glide_Collide":
            callers.add(m.group(2))
    assert callers == {"PState_Glide", "PState_GlideFall"}, (
        f"Glide_Collide's callers are {sorted(callers)}, not the two glide "
        f"states. The 'Knuckles only' scope claim no longer holds.")

    # and the glide family is entered only through Knuckles' ability pointer
    ability_sites = []
    for path in (KNUCKLES_EMP,
                 os.path.join(ROOT, "games", "sonic4", "player", "sonic.emp"),
                 os.path.join(ROOT, "games", "sonic4", "player", "tails.emp")):
        if not os.path.exists(path):
            continue
        if "Ability_KnuxGlide" in _read(path, "chardef"):
            ability_sites.append(os.path.basename(path))
    assert ability_sites == ["knuckles.emp"], (
        f"Ability_KnuxGlide is referenced by chardefs {ability_sites}; the "
        f"glide is supposed to be reachable from Knuckles alone.")
