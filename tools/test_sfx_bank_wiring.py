"""Wiring gates for the SFX bank's THREE hand-maintained mirrors.

Adding an SFX means editing four places that no compiler cross-checks:

    games/sonic4/config/sound_ids.emp     SFXID_* value + SFXPRI_* tier
    tools/sfx_transcode.py                _CORE_SFX_IDS + _SFX_PRIORITY
    games/sonic4/data/sound/sfx/sfx_bank.emp    one `table` row
    games/sonic4/data/sound/sfx_blob_win_tab.emp  one cell, at the right INDEX

sfx_bank.emp's own `ensure` covers the win-tab's total SPAN, and the co-link byte
gate covers the emitted body length — but NOTHING checks that a cell sits at the
index its id demands, or that the transcoder's priority for an id matches the
value the game declares. A cell one slot out of place is silent: the id resolves
to a neighbouring blob (or to a hole, i.e. no sound) with no diagnostic anywhere.
That is what these tests close.

Everything asserted here is DERIVED from the four files at run time. There are no
copied constants: the expected index of id N is computed as N - SFX_ID_BASE where
SFX_ID_BASE is itself read out of the table's own key range.

    python3 -m pytest tools/test_sfx_bank_wiring.py -q
"""

import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

SOUND_IDS_EMP = os.path.join(ROOT, "games", "sonic4", "config", "sound_ids.emp")
SFX_BANK_EMP = os.path.join(ROOT, "games", "sonic4", "data", "sound", "sfx",
                            "sfx_bank.emp")
WIN_TAB_EMP = os.path.join(ROOT, "games", "sonic4", "data", "sound",
                           "sfx_blob_win_tab.emp")
SFX_DIR = os.path.join(ROOT, "games", "sonic4", "data", "sound", "sfx")


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _emp_int(tok):
    tok = tok.strip()
    return int(tok[1:], 16) if tok.startswith("$") else int(tok, 0)


# --- parsers over the four authorities ------------------------------------

def parse_sound_ids():
    """-> ({name: value} for SFXID_*, {name: value} for SFXPRI_*)."""
    src = _read(SOUND_IDS_EMP)
    ids, pris = {}, {}
    for m in re.finditer(r"^pub const (SFXID_\w+)\s*:\s*SfxId\s*=\s*(\$?\w+)",
                         src, re.M):
        name, val = m.group(1), m.group(2)
        if val.startswith("SFXID_"):
            continue                      # an alias (SFXID_REV_LOOP); resolved below
        ids[name] = _emp_int(val)
    for m in re.finditer(r"^pub const (SFXPRI_\w+)\s*=\s*(\$\w+)", src, re.M):
        pris[m.group(1)] = _emp_int(m.group(2))
    return ids, pris


def parse_bank_rows():
    """-> (key_lo, key_hi, {id: blob_filename}) from sfx_bank.emp's `table`."""
    src = _read(SFX_BANK_EMP)
    m = re.search(r"table SfxTable \(cell:.*?key:\s*(\$\w+)\.\.=(\$\w+)", src)
    assert m, "sfx_bank.emp: could not find the SfxTable key range"
    lo, hi = _emp_int(m.group(1)), _emp_int(m.group(2))
    rows = {}
    for rm in re.finditer(r"^\s*(\$\w+):\s*Sfx_\w+ = embed\(\"([^\"]+)\"\)", src, re.M):
        rows[_emp_int(rm.group(1))] = rm.group(2)
    return lo, hi, rows


def parse_win_tab():
    """-> (cells, declared_span). cells is the flat list of body tokens."""
    src = _read(WIN_TAB_EMP)
    body = src.split("pub proc SfxBlobWinTab () clobbers() {")[1].split("\n    }")[0]
    cells = []
    for line in body.splitlines():
        line = line.split("//")[0].strip()
        if not line.startswith("dc.w"):
            continue
        cells.extend(t.strip() for t in line[4:].split(",") if t.strip())
    sm = re.search(r"^ensure\((\d+) == extern\(\"SFX_TABLE_LEN\"\)", src, re.M)
    assert sm, "sfx_blob_win_tab.emp: could not find the span ensure"
    return cells, int(sm.group(1))


# --- the gates -------------------------------------------------------------

def test_win_tab_cell_count_matches_the_key_range():
    """The emitted body must have exactly max_id - min_id + 1 cells.

    sfx_bank.emp's own guard compares the DECLARED span literal against
    SFX_TABLE_LEN and explicitly cannot see the emitted body (its comment says
    so). This closes that hole from the other side, off the same key range.
    """
    lo, hi, _ = parse_bank_rows()
    cells, declared = parse_win_tab()
    assert len(cells) == hi - lo + 1, (
        f"SfxBlobWinTab emits {len(cells)} cells but the SfxTable key range "
        f"${lo:02X}..${hi:02X} needs {hi - lo + 1}")
    assert declared == hi - lo + 1, (
        f"the span ensure declares {declared}, the key range needs {hi - lo + 1}")


def test_every_win_tab_cell_sits_at_its_own_id_index():
    """SFX_WIN_NN must be cell number $NN - SFX_ID_BASE, and every other cell 0.

    THE failure this exists for: a miscounted zero run shifts a pointer by one
    slot, and the id then resolves to its neighbour's blob (or to a hole = no
    sound at all) with nothing anywhere reporting it.
    """
    lo, _hi, rows = parse_bank_rows()
    cells, _ = parse_win_tab()
    named = {}
    for idx, tok in enumerate(cells):
        if tok == "0":
            continue
        m = re.fullmatch(r"SFX_WIN_([0-9A-F]{2})", tok)
        assert m, f"cell {idx}: unexpected token {tok!r} (want 0 or SFX_WIN_NN)"
        sfx_id = int(m.group(1), 16)
        assert idx == sfx_id - lo, (
            f"SFX_WIN_{m.group(1)} is cell {idx}, but id ${sfx_id:02X} indexes "
            f"cell {sfx_id - lo} (SfxBlobWinTab[id - ${lo:02X}])")
        named[sfx_id] = tok
    assert set(named) == set(rows), (
        "the win table and the SfxTable rows name different id sets: "
        f"only in win tab {sorted(set(named) - set(rows))}, "
        f"only in bank {sorted(set(rows) - set(named))}")


def test_bank_rows_are_ascending_and_their_blobs_exist():
    """sfx_bank.emp documents an ascending-key rule (the payload order); and an
    embed of a missing .bin is a build error, but a row pointing at the WRONG
    id's file is not."""
    _lo, _hi, rows = parse_bank_rows()
    src = _read(SFX_BANK_EMP)
    order = [int(m.group(1), 16) for m in
             re.finditer(r"^\s*\$(\w+):\s*Sfx_\w+ = embed\(", src, re.M)]
    assert order == sorted(order), f"SfxTable rows are not in ascending key order: {order}"
    for sfx_id, fname in rows.items():
        assert fname == f"sfx_{sfx_id:02X}.bin", (
            f"row ${sfx_id:02X} embeds {fname!r}, not its own blob")
        assert os.path.exists(os.path.join(SFX_DIR, fname)), f"{fname} is missing"


def test_transcoder_and_game_agree_on_the_id_set():
    """_CORE_SFX_IDS, the SfxTable rows and the SFXID_* declarations are three
    hand-written spellings of one set."""
    import sys
    sys.path.insert(0, HERE)
    from sfx_transcode import _CORE_SFX_IDS
    ids, _ = parse_sound_ids()
    _lo, _hi, rows = parse_bank_rows()
    assert set(_CORE_SFX_IDS) == set(rows), (
        f"_CORE_SFX_IDS vs SfxTable rows: only in tool "
        f"{sorted(set(_CORE_SFX_IDS) - set(rows))}, only in bank "
        f"{sorted(set(rows) - set(_CORE_SFX_IDS))}")
    assert set(ids.values()) == set(rows), (
        f"SFXID_* values vs SfxTable rows: only declared "
        f"{sorted(set(ids.values()) - set(rows))}, only in bank "
        f"{sorted(set(rows) - set(ids.values()))}")


def test_transcoder_priority_map_mirrors_the_game_tiers():
    """sfx_transcode.py BAKES a priority byte into every SfxHeader from its own
    copy of the SFXPRI_* ladder. sound_ids.emp calls that copy a mirror; until
    now nothing compared them, so a tier edited on one side alone would ship a
    header byte disagreeing with the declared ladder."""
    import sys
    sys.path.insert(0, HERE)
    import sfx_transcode
    _, pris = parse_sound_ids()
    for name, val in pris.items():
        assert hasattr(sfx_transcode, name), (
            f"{name} is declared in sound_ids.emp but absent from sfx_transcode.py, "
            f"whose docstring calls itself a mirror of that ladder")
        assert getattr(sfx_transcode, name) == val, (
            f"{name}: sound_ids.emp says {val:#04x}, sfx_transcode.py says "
            f"{getattr(sfx_transcode, name):#04x}")


def test_every_shipped_blob_header_carries_its_declared_priority():
    """END-TO-END: byte 0 of each sfx_NN.bin is sfh_priority. Check it against
    the tier sound_ids.emp declares for that id, resolved through the transcoder's
    id->tier map. This is the only test that reads the SHIPPED bytes."""
    import sys
    sys.path.insert(0, HERE)
    from sfx_transcode import _SFX_PRIORITY
    _, pris = parse_sound_ids()
    _lo, _hi, rows = parse_bank_rows()
    declared = set(pris.values())
    for sfx_id, fname in sorted(rows.items()):
        with open(os.path.join(SFX_DIR, fname), "rb") as f:
            got = f.read(1)[0]
        assert sfx_id in _SFX_PRIORITY, f"${sfx_id:02X} has no priority tier"
        want = _SFX_PRIORITY[sfx_id]
        assert got == want, (
            f"{fname} sfh_priority is ${got:02X}, the map says ${want:02X} — "
            f"the blob is stale; re-run `python3 tools/sfx_transcode.py generate "
            f"--emit-bin`")
        assert want in declared, (
            f"${sfx_id:02X} is baked with ${want:02X}, which is not any SFXPRI_* "
            f"tier declared in sound_ids.emp")
        assert got & 0x80 == 0, (
            f"{fname} sfh_priority ${got:02X} has bit 7 set — that bit is the "
            f"non-latching flag, not part of the rank")


def test_psgform_sfx_ship_the_tracked_noise_shape():
    """END-TO-END (B5): every shipped blob whose S3K SOURCE carries smpsPSGform must
    contain that form byte as MEV_PSGNOISE, and must NOT contain the pre-B5 baked
    fixed-rate note. The SET of such ids is DISCOVERED by scanning the skdisasm
    sources the transcoder reads — nothing here is a copied id list, so a new
    smpsPSGform SFX is covered the moment it is added to _CORE_SFX_IDS.

    This is the only test that reads the SHIPPED bytes for the noise shape. It is the
    producer end of the chain the engine closes: MEV_PSGNOISE -> Seq_Op_PsgNoise's SFX
    arm (control byte + tone-3 silence, no sc_noise_mode store) -> a noise NOTE that is
    a PITCH -> Psg_NoteOn -> Psg_EmitDivisor's CHROUTE_PSGN latch ($C0 = the rate-3
    noise clock) -> Psg_ApplyMod sweeping that same latch."""
    import sys
    sys.path.insert(0, HERE)
    import sfx_transcode as T
    from song_packer import MEV_PSGNOISE, MEV_MODSET

    skd = os.environ.get("AEON_SKDISASM_DIR") or T.SKDISASM_SFX_DIR
    sfx_src_dir = skd if os.path.basename(skd).upper() == "SFX" else \
        os.path.join(skd, "Sound", "SFX")
    if not os.path.isdir(sfx_src_dir):
        # LOUD, not green: the discovery scan cannot run without the sources.
        raise AssertionError(
            f"cannot read the S3K SFX sources at {sfx_src_dir} — this gate DISCOVERS "
            f"its subject set by scanning them, so it cannot be evaluated. Set "
            f"AEON_SKDISASM_DIR.")

    _, _, rows = parse_bank_rows()
    tracked = {}
    for sfx_id in sorted(rows):
        fname = T._CORE_SFX_FILENAMES.get(sfx_id)
        if fname is None:
            continue
        path = os.path.join(sfx_src_dir, fname)
        if not os.path.exists(path):
            raise AssertionError(f"missing S3K source {path} for ${sfx_id:02X}")
        src = _read(path)
        forms = re.findall(r'smpsPSGform\s+\$([0-9A-Fa-f]{2})', src)
        if forms:
            tracked[sfx_id] = ([int(f, 16) for f in forms], 'smpsModSet' in src)

    assert tracked, (
        "no shipped SFX source carries smpsPSGform — the scan found nothing to "
        "check, so this gate would be vacuous")

    for sfx_id, (forms, src_has_modset) in sorted(tracked.items()):
        blob = open(os.path.join(SFX_DIR, rows[sfx_id]), "rb").read()
        for form in forms:
            assert form & 3 == 3, (
                f"${sfx_id:02X} source carries smpsPSGform ${form:02X}, a PRESET rate; "
                f"the engine has no SFX path for one (B5)")
            assert bytes([MEV_PSGNOISE, form]) in blob, (
                f"{rows[sfx_id]} does not carry MEV_PSGNOISE ${form:02X} — the source's "
                f"smpsPSGform was dropped (the pre-B5 v1 approximation). Re-run "
                f"`python3 tools/sfx_transcode.py generate --emit-bin`")
        # The pre-B5 shape baked the fixed rate into a NoteDur and DROPPED the sweep.
        # $B6/$42/$7E all carry a smpsModSet, so its absence is the same regression.
        if src_has_modset:
            assert MEV_MODSET in blob, (
                f"{rows[sfx_id]} carries no MEV_MODSET though its source has a "
                f"smpsModSet — the noise reroute dropped the sweep (pre-B5 behaviour)")
