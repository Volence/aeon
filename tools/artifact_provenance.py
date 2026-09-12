#!/usr/bin/env python3
"""artifact_provenance — the ONE freshness verdict for a (.bin, .lst) build pair (LS-1a).

WHAT IT REPLACES. Until 2026-09-12 fourteen build-time consumers decided a pair was fresh
by `mtime >= ${SIGIL_T0}`, each parsing the flag and doing the comparison privately. That
is PROVENANCE, not content: a `touch`, or an unrelated command rewriting the file after the
build began, reads as fresh. And the fourteen disagreed on what a stale pair MEANT: most
exited 2 (unmeasurable), three exited 1 (instashield_gate, loop_crossover_gate and
bganim_room, whose `main` maps every Unmeasurable to 1), and sprite_tilt_gate returned 0
when `--gate` was omitted. Every one of them now calls `check_pair` here, and gets the same
answer in the same words with the same exit code.

WHAT IT READS. Since sigil `13ca9425` (installed at `6884bfba`, 2026-09-12) every `.lst`
sigil writes opens with a Source Digest section: the assembler's identity, the build
shape, the define environment, the `*.emp` module scan, one `DIGEST-READ` row per file the
build read (crc32, size, path), an aggregate over those rows, and `DIGEST-ROM`, the CRC,
size and path of the ROM the build wrote. The grammar is sigil's
`docs/superpowers/notes/2026-09-11-lst-source-digest.md` (section 1) and its emitter
`crates/sigil-link/src/listing.rs` (`emit_source_digest`); this module's parser was checked
against listings the installed assembler actually wrote, not against the note alone.

THE VERDICT. A pair is FRESH (exit 0) only when ALL of these hold, and NOT FRESH (exit 2,
COULD NOT RUN: the caller did not measure the artifact it was asked about) otherwise.
Every problem is reported, each naming the row or file that disagrees:

  1. both files exist;
  2. the listing carries exactly one contiguous `DIGEST-` section, found by `^DIGEST-`
     and never by position, closed by `DIGEST-END` (a section without it was TRUNCATED),
     in format 1, internally consistent (the AGGREGATE recomputes from the READ rows);
  3. `DIGEST-ROM` names the pair's .bin (path resolved under its root), and its crc32 and
     size equal the .bin's;
  4. every `DIGEST-READ` row's file exists with that crc32 and size, `origin=generated`
     and `origin=tool` rows included;
  5. re-running the module walk's rule over the aeon root today reproduces `DIGEST-SCAN`
     (a module that APPEARED after the build has no READ row, and the next build would
     read it; the scan is the only absence-sensitive input);
  6. `DIGEST-ASSEMBLER revision=` equals the running `$SIGIL_BUILD --version` revision
     (decision (a), below);
  7. `DIGEST-SHAPE` game and debug equal what the caller expects: passed explicitly by a
     gate that takes `--shape`/`--game`, otherwise derived from a canonical artifact name
     (`s4.bin`, `s4.debug.bin`, `demo.bin`, `demo.debug.bin`); a non-canonical name is
     reported as unchecked, never guessed;
  8. with `built_after`, both files were written at or after it (decision (b), below).

  `tree=` is REPORTED and never gated on, but an unknown word there fails CLOSED: the
  vocabulary is `clean`, `clean-sources`, `dirty`, `unknown` (sigil's `tree_class.rs`,
  which tells consumers to match the trusted words positively for exactly this reason).

DECISION (a): the assembler revision IS checked. Content equality alone passes a listing
an OLDER assembler built from identical sources, and 2026-09-12 is the proof that this
happens: the shared pair was swapped under every lane that morning, which changed deb2
bytes with no aeon edit. The check costs one `--version` spawn (~2 ms). The shape is
checked too, because three of the gates assert OPPOSITE things per shape
(plane_base_swap_gate's own docstring) and a mis-shaped artifact under a canonical name
would get a confident wrong verdict. With no assembler to ask (SIGIL_BUILD unset) the
pair is NOT FRESH: "which assembler should have written this" has no answer, and an
unanswered question is not a pass.

DECISION (b): `built_after` SURVIVES as an additional condition wherever the caller has
one. It proves "this run wrote it", which the digest cannot: the assembler's own binary is
not a READ row, so two binaries at one revision (a `dirty` rebuild, or a relink in place)
produce listings the digest cannot tell apart, and only "written after this run started
its own $SIGIL_BUILD" separates them. It also keeps build.sh's post-sigil lane deferring
every artifact the current shape did not write, which is what that lane is documented to
do. Both conditions must hold; neither alone is freshness.

DECISION (c): "no section" is NEVER green. A listing with no `DIGEST-` line is NOT FRESH
naming the reason, whatever its mtime. In build.sh every consumer runs after the sigil
build, which writes the listing last (after the ROM is final), so on a fresh clone the
listing is always newly written and carries a section; the unmeasurable path is only
reachable by a listing some other process wrote.

WHEN IT RUNS. When the caller asks a provenance question: a gate's `--built-after`, the
conftest lane's `--artifacts-built-after`, or this file's CLI. A hand run of a gate without
the flag still grades whatever is on disk, as before; that is a hand run's contract, and
it is stated rather than changed here.

CLI:  artifact_provenance.py --rom s4.debug.bin --lst s4.debug.lst [--built-after EPOCH]
                             [--root DIR] [--game G --debug 0|1]
      exit 0 FRESH, exit 2 NOT FRESH (every problem printed), nothing else.
"""

import argparse
import os
import re
import subprocess
import sys
import zlib

#: The exit codes, matching tools/needs_build_lane.py's contract: 0 fresh, 2 COULD NOT
#: RUN. There is no 1 here on purpose. A stale pair is not a failed measurement, it is the
#: absence of one, and a 1 would tell the caller the bytes were measured and are wrong.
FRESH = 0
UNMEASURABLE = 2

AEON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: The one digest format this parser reads. A different number is a grammar it does not
#: know, and it refuses rather than guesses.
DIGEST_FORMAT = "1"

#: sigil's tree-state vocabulary (crates/sigil-cli/src/tree_class.rs, `state_and_detail`,
#: plus build.rs's `unknown` fallback). Matched POSITIVELY: any other word is refused.
KNOWN_TREE_WORDS = ("clean", "clean-sources", "dirty", "unknown")

#: The canonical artifact names build.sh writes, and the shape each one must carry.
CANONICAL_SHAPES = {
    "s4.bin": ("sonic4", 0),
    "s4.debug.bin": ("sonic4", 1),
    "demo.bin": ("demo", 0),
    "demo.debug.bin": ("demo", 1),
}

KEYWORDS = ("FORMAT", "ASSEMBLER", "SHAPE", "DEFINE", "SCAN", "READ", "AGGREGATE", "ROM",
            "END")
#: The section's line kinds in the order the grammar allows them.
_ORDER = re.compile(r"^FASD*CR+GME$")
_KIND_CODE = {"FORMAT": "F", "ASSEMBLER": "A", "SHAPE": "S", "DEFINE": "D", "SCAN": "C",
              "READ": "R", "AGGREGATE": "G", "ROM": "M", "END": "E"}
_HEX8 = re.compile(r"^[0-9a-f]{8}$")
_ROOTS = ("sigil", "filesystem")
_ORIGINS = ("source", "generated", "tool", "external")

#: How many problems a message lists before it summarises the rest.
MAX_LISTED = 25


class DigestError(Exception):
    """The listing carries no usable Source Digest. The message says why."""


# ---------------------------------------------------------------------------
# Reading the section
# ---------------------------------------------------------------------------

def crc32(data):
    return zlib.crc32(data) & 0xFFFFFFFF


def _fields(text, line):
    """`key=value` tokens found by KEY, never by position (the note's rule)."""
    out = {}
    for tok in text.split(" "):
        if "=" not in tok:
            raise DigestError(f"digest line `{line}` carries `{tok}`, which is not key=value")
        k, v = tok.split("=", 1)
        if k in out:
            raise DigestError(f"digest line `{line}` repeats the field `{k}`")
        out[k] = v
    return out


def _need(fields, keys, line):
    missing = [k for k in keys if k not in fields]
    if missing:
        raise DigestError(f"digest line `{line}` lacks the field(s) {missing}")


def _hex8(v, line):
    if not _HEX8.match(v):
        raise DigestError(f"digest line `{line}` carries `{v}` where 8 lowercase hex digits belong")
    return int(v, 16)


def _dec(v, line):
    if not v.isdigit():
        raise DigestError(f"digest line `{line}` carries `{v}` where a decimal count belongs")
    return int(v)


def _split_path(body, line):
    """(fixed-fields text, path). `path=` is the LAST field and runs to end of line."""
    if " path=" not in body:
        return body, None
    fixed, path = body.split(" path=", 1)
    parts = path.split("/")
    if not path or path.startswith("/") or any(p in ("", ".", "..") for p in parts):
        raise DigestError(f"digest line `{line}` names `{path}`, which is not a relative "
                          f"path without empty, `.` or `..` components")
    return fixed, path


def read_digest(lst_path):
    """The Source Digest of `lst_path`, as a dict. Raises DigestError, naming the reason,
    for a listing with no section, a truncated one, a second one, an unknown format or
    keyword, a malformed row, or an aggregate its READ rows do not reproduce."""
    with open(lst_path, "rb") as f:
        raw = f.read()
    lines = raw.split(b"\n")
    at = [i for i, ln in enumerate(lines) if ln.startswith(b"DIGEST-")]
    if not at:
        raise DigestError(
            "the listing has NO `DIGEST-` section, so nothing ties it to the sources or to "
            "a ROM. It was written by an assembler older than sigil 13ca9425, or by "
            "something other than `sigil build`, or the section was stripped")
    if at != list(range(at[0], at[0] + len(at))):
        gap = next(a for a, b in zip(at, at[1:]) if b != a + 1)
        raise DigestError(
            f"the `DIGEST-` lines are not one contiguous section (a non-digest line follows "
            f"line {gap + 1}), so it is two sections or a damaged one")
    section = []
    for i in at:
        try:
            section.append(lines[i].decode("utf-8"))
        except UnicodeDecodeError:
            raise DigestError(f"digest line {i + 1} is not UTF-8")
    # A section cut short ends without its END line, and a file cut mid-line leaves the
    # last digest line without its LF (split() then makes it the file's final element).
    if "DIGEST-END" not in section:
        raise DigestError(
            f"the section has no `DIGEST-END` line: it is TRUNCATED after "
            f"{len(section)} line(s) (last: `{section[-1][:100]}`)")
    if section[-1] != "DIGEST-END":
        raise DigestError("`DIGEST-` lines follow `DIGEST-END`, so the section's end is not "
                          "where its END line says")

    kinds = []
    for ln in section:
        kw = ln[len("DIGEST-"):].split(" ", 1)[0]
        if kw not in KEYWORDS:
            raise DigestError(f"digest line `{ln[:100]}` has the unknown keyword `{kw}`, "
                              f"which format {DIGEST_FORMAT} does not define")
        kinds.append(kw)
    if _ORDER.match("".join(_KIND_CODE[k] for k in kinds)) is None:
        raise DigestError(
            "the section's lines are not in the grammar's order "
            "(FORMAT ASSEMBLER SHAPE DEFINE* SCAN READ+ AGGREGATE ROM END); found "
            + " ".join(dict.fromkeys(kinds)))

    d = {"defines": {}, "reads": []}
    read_bytes = []
    for ln, kw in zip(section, kinds):
        body = ln[len("DIGEST-") + len(kw) + 1:] if kw != "END" else ""
        if kw == "FORMAT":
            if body != DIGEST_FORMAT:
                raise DigestError(f"`{ln}`: this reader knows format {DIGEST_FORMAT} only, "
                                  f"and refuses rather than guesses at another grammar")
        elif kw == "ASSEMBLER":
            if not body.startswith("sigil "):
                raise DigestError(f"`{ln}` does not name the sigil assembler")
            f = _fields(body[len("sigil "):], ln)
            _need(f, ("version", "revision", "tree"), ln)
            d["assembler"] = f
        elif kw == "SHAPE":
            f = _fields(body, ln)
            _need(f, ("target", "game", "debug", "extra-entries"), ln)
            if f["debug"] not in ("0", "1"):
                raise DigestError(f"`{ln}` has debug={f['debug']}, not 0 or 1")
            d["shape"] = f
        elif kw == "DEFINE":
            if "=" not in body or " " in body:
                raise DigestError(f"`{ln}` is not one NAME=INT token")
            name, value = body.split("=", 1)
            d["defines"][name] = value
        elif kw == "SCAN":
            f = _fields(body, ln)
            _need(f, ("pattern", "files", "crc"), ln)
            if f["pattern"] != "*.emp":
                raise DigestError(f"`{ln}` scans `{f['pattern']}`; this reader knows only the "
                                  f"`*.emp` module walk and cannot reproduce another")
            d["scan"] = {"files": _dec(f["files"], ln), "crc": _hex8(f["crc"], ln), "line": ln}
        elif kw == "READ":
            fixed, path = _split_path(body, ln)
            if path is None:
                raise DigestError(f"`{ln}` carries no path= field")
            f = _fields(fixed, ln)
            _need(f, ("crc", "size", "origin"), ln)
            if f["origin"] not in _ORIGINS:
                raise DigestError(f"`{ln}` has the unknown origin `{f['origin']}`")
            root = f.get("root")
            if root is not None and root not in _ROOTS:
                raise DigestError(f"`{ln}` names the unknown root `{root}`")
            if (f["origin"] == "external") != (root is not None):
                raise DigestError(f"`{ln}`: a row carries root= exactly when it is "
                                  f"origin=external, and this one does not")
            d["reads"].append({"crc": _hex8(f["crc"], ln), "size": _dec(f["size"], ln),
                               "origin": f["origin"], "root": root, "path": path,
                               "line": ln})
            read_bytes.append(ln.encode("utf-8") + b"\n")
        elif kw == "AGGREGATE":
            f = _fields(body, ln)
            _need(f, ("crc", "reads"), ln)
            claimed, count = _hex8(f["crc"], ln), _dec(f["reads"], ln)
            actual = crc32(b"".join(read_bytes))
            if claimed != actual or count != len(read_bytes):
                raise DigestError(
                    f"`{ln}` does not match its own READ rows (they give crc={actual:08x} "
                    f"reads={len(read_bytes)}): the section was edited or damaged after "
                    f"sigil wrote it")
        elif kw == "ROM":
            fixed, path = _split_path(body, ln)
            if path is None:
                if not fixed.endswith(" output=none"):
                    raise DigestError(f"`{ln}` carries neither path= nor output=none")
                raise DigestError(
                    f"`{ln}`: the build that wrote this listing wrote NO ROM (no -o), so the "
                    f"listing cannot vouch for any .bin")
            f = _fields(fixed, ln)
            _need(f, ("crc", "size"), ln)
            root = f.get("root")
            if root is not None and root not in _ROOTS:
                raise DigestError(f"`{ln}` names the unknown root `{root}`")
            d["rom"] = {"crc": _hex8(f["crc"], ln), "size": _dec(f["size"], ln),
                        "root": root, "path": path, "line": ln}
    return d


# ---------------------------------------------------------------------------
# Reproducing the module scan
# ---------------------------------------------------------------------------

def _rust_extension(name):
    """`Path::extension` as Rust defines it: None for no dot, or a leading dot only."""
    i = name.rfind(".")
    if i <= 0:
        return None
    return name[i + 1:]


def scan_members(root):
    """The `.emp` module walk's membership, by sigil's rule, as `/`-joined paths relative
    to `root` in the spelling the walk built (crates/sigil-frontend-emp/src/resolve/
    manifest.rs, `collect_emp` and `is_nested_checkout_dir`):

      recursive from the root; a directory entry is judged by its OWN type, so a symlink
      to a directory is not followed (and, being a non-directory entry, counts if its name
      ends `.emp`); a child directory named `.worktrees`, or one holding a `.git` entry,
      is not entered (the root itself always is); an unreadable subdirectory is skipped;
      every non-directory entry whose extension is exactly `emp` is a member.
    """
    out = []

    def walk(d, rel):
        try:
            entries = list(os.scandir(d))
        except OSError:
            if not rel:
                raise
            return
        for e in entries:
            try:
                is_dir = e.is_dir(follow_symlinks=False)
            except OSError:
                is_dir = False
            sub = rel + "/" + e.name if rel else e.name
            if is_dir:
                if e.name == ".worktrees" or os.path.exists(os.path.join(e.path, ".git")):
                    continue
                walk(e.path, sub)
            elif _rust_extension(e.name) == "emp":
                out.append(sub)

    walk(root, "")
    return sorted(out, key=lambda s: s.encode("utf-8", "surrogateescape"))


def scan_identity(members):
    """`DIGEST-SCAN`'s (files, crc): CRC-32 over the paths sorted by bytes, each + LF."""
    text = "".join(m + "\n" for m in members)
    return len(members), crc32(text.encode("utf-8", "surrogateescape"))


# ---------------------------------------------------------------------------
# The assembler
# ---------------------------------------------------------------------------

def assembler_identity(assembler):
    """(revision, tree word, source root) from `<assembler> --version`. Raises
    DigestError when it cannot be asked or does not answer in the known shape."""
    try:
        p = subprocess.run([assembler, "--version"], capture_output=True, text=True,
                           timeout=60)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise DigestError(f"could not run `{assembler} --version`: {e}")
    if p.returncode != 0:
        raise DigestError(f"`{assembler} --version` exited {p.returncode}")
    got = {}
    for ln in p.stdout.splitlines():
        m = re.match(r"^\s+(revision|tree|source):\s+(\S+)", ln)
        if m and m.group(1) not in got:
            got[m.group(1)] = m.group(2)
    if "revision" not in got or "source" not in got:
        raise DigestError(f"`{assembler} --version` printed no `revision:`/`source:` line, "
                          f"so the assembler's identity is unknown")
    return got["revision"], got.get("tree", "?"), got["source"]


# ---------------------------------------------------------------------------
# The verdict
# ---------------------------------------------------------------------------

class Verdict:
    """What `check_pair` found. `code` is FRESH (0) or UNMEASURABLE (2); `problems` names
    every disagreement (empty exactly when fresh); `notes` are reported facts."""

    def __init__(self, rom, lst):
        self.rom, self.lst = rom, lst
        self.problems, self.notes = [], []
        self.digest = None

    @property
    def fresh(self):
        return not self.problems

    @property
    def code(self):
        return FRESH if self.fresh else UNMEASURABLE

    def render(self, tool):
        """The one wording every consumer prints."""
        pair = f"{self.lst} + {self.rom}"
        if self.fresh:
            return f"{tool}: provenance FRESH — {pair} ({'; '.join(self.notes)})"
        head = (f"{tool}: provenance NOT FRESH — {pair} is not a pair this build can be "
                f"graded on; exit {UNMEASURABLE} (COULD NOT RUN: the artifact asked about "
                f"was not measured). {len(self.problems)} problem(s):")
        rows = [f"  - {p}" for p in self.problems[:MAX_LISTED]]
        if len(self.problems) > MAX_LISTED:
            rows.append(f"  - ... and {len(self.problems) - MAX_LISTED} more")
        tail = [f"  ({n})" for n in self.notes]
        return "\n".join([head] + rows + tail)


def expected_shape(rom):
    """(game, debug) a canonical artifact name must carry, or None for any other name."""
    return CANONICAL_SHAPES.get(os.path.basename(rom))


def _resolve(root_word, path, aeon, sigil_root):
    if root_word is None:
        return os.path.join(aeon, path)
    if root_word == "filesystem":
        return "/" + path
    return os.path.join(sigil_root, path)


def check_pair(rom, lst, *, built_after=None, root=None, assembler=None,
               expect_game=None, expect_debug=None):
    """The freshness verdict for the pair (`rom`, `lst`). See the module docstring.

    `root` is the aeon root the digest's unrooted paths are relative to (default: the tree
    this file lives in). `assembler` is the sigil binary whose revision the listing must
    carry (default: $SIGIL_BUILD). `expect_game`/`expect_debug` override the shape a
    canonical name implies."""
    v = Verdict(rom, lst)
    aeon = os.path.realpath(root if root is not None else AEON)
    missing = [p for p in (lst, rom) if not os.path.isfile(p)]
    for p in missing:
        v.problems.append(f"{p} does not exist")
    if missing:
        return v

    # (b) provenance: this run wrote both files.
    if built_after is not None:
        for p in (lst, rom):
            m = os.stat(p).st_mtime
            if m < float(built_after):
                v.problems.append(
                    f"{p} was written at {m:.0f}, before this build began ({float(built_after):.0f}): "
                    f"a previous invocation's artifact")

    try:
        d = read_digest(lst)
    except (DigestError, OSError) as e:
        v.problems.append(f"{lst}: {e}")
        return v
    v.digest = d
    asm = d["assembler"]
    if asm["tree"] not in KNOWN_TREE_WORDS:
        v.problems.append(
            f"DIGEST-ASSEMBLER tree={asm['tree']} is not one of {list(KNOWN_TREE_WORDS)}; the "
            f"vocabulary grew and this reader fails closed rather than trust an unknown word")

    # (a) the assembler that wrote it is the one this build runs.
    exe = assembler if assembler is not None else os.environ.get("SIGIL_BUILD")
    sigil_root = None
    if not exe:
        v.problems.append(
            "SIGIL_BUILD is unset, so there is no assembler to compare DIGEST-ASSEMBLER "
            f"revision={asm['revision'][:12]} against, and the listing's `root=sigil` rows "
            "have no root to resolve under")
    else:
        try:
            rev, tree, sigil_root = assembler_identity(exe)
        except DigestError as e:
            v.problems.append(str(e))
        else:
            if rev != asm["revision"]:
                v.problems.append(
                    f"DIGEST-ASSEMBLER revision={asm['revision']} but the running assembler "
                    f"{exe} is revision {rev}: the listing was written by another assembler")
            v.notes.append(f"assembler {asm['revision'][:8]} tree={asm['tree']} "
                           f"(running binary: tree={tree}; tree is reported, not gated)")

    # The shape the caller expects.
    shape = d["shape"]
    want = expected_shape(rom)
    game = expect_game if expect_game is not None else (want[0] if want else None)
    debug = expect_debug if expect_debug is not None else (want[1] if want else None)
    if game is not None and shape["game"] != game:
        v.problems.append(f"DIGEST-SHAPE game={shape['game']}, but {os.path.basename(rom)} "
                          f"must be game={game}")
    if debug is not None and shape["debug"] != str(int(bool(debug))):
        v.problems.append(f"DIGEST-SHAPE debug={shape['debug']}, but "
                          f"{os.path.basename(rom)} must be debug={int(bool(debug))}")
    if game is None and debug is None:
        v.notes.append(f"shape not checked: {os.path.basename(rom)} is not a canonical "
                       f"artifact name and the caller named no shape")

    # DIGEST-ROM names this .bin, by path, crc and size.
    r = d["rom"]
    if r["root"] == "sigil" and sigil_root is None:
        v.problems.append(f"{r['line']}: its root=sigil path cannot be resolved without the "
                          f"assembler's source root")
    else:
        named = os.path.realpath(_resolve(r["root"], r["path"], aeon, sigil_root))
        if named != os.path.realpath(rom):
            v.problems.append(f"DIGEST-ROM names {named}, not {os.path.realpath(rom)}: this "
                              f"listing belongs to another ROM file")
    with open(rom, "rb") as f:
        data = f.read()
    if (crc32(data), len(data)) != (r["crc"], r["size"]):
        v.problems.append(f"DIGEST-ROM says crc={r['crc']:08x} size={r['size']} but {rom} is "
                          f"crc={crc32(data):08x} size={len(data)}")

    # Every file the build read, as it was read.
    for row in d["reads"]:
        if row["root"] == "sigil" and sigil_root is None:
            v.problems.append(f"DIGEST-READ root=sigil path={row['path']}: no assembler "
                              f"source root to resolve it under")
            continue
        p = _resolve(row["root"], row["path"], aeon, sigil_root)
        try:
            with open(p, "rb") as f:
                data = f.read()
        except OSError as e:
            v.problems.append(f"DIGEST-READ path={row['path']}: the file the build read is "
                              f"gone ({e.strerror})")
            continue
        if (crc32(data), len(data)) != (row["crc"], row["size"]):
            v.problems.append(
                f"DIGEST-READ path={row['path']} (origin={row['origin']}): the build read "
                f"crc={row['crc']:08x} size={row['size']}, the file is now "
                f"crc={crc32(data):08x} size={len(data)}")

    # The module walk reproduces.
    try:
        members = scan_members(aeon)
    except OSError as e:
        v.problems.append(f"DIGEST-SCAN: the aeon root {aeon} cannot be walked ({e})")
    else:
        files, crc = scan_identity(members)
        sc = d["scan"]
        if (files, crc) != (sc["files"], sc["crc"]):
            read_paths = {row["path"] for row in d["reads"] if row["root"] is None}
            appeared = [m for m in members if m not in read_paths]
            detail = (f"; module(s) with no READ row, i.e. new since the build: "
                      f"{', '.join(appeared[:10])}" if appeared else "")
            v.problems.append(f"DIGEST-SCAN files={sc['files']} crc={sc['crc']:08x}, but "
                              f"the walk finds files={files} crc={crc:08x} today{detail}")

    if v.fresh:
        v.notes.insert(0, f"DIGEST-ROM crc={r['crc']:08x} size={r['size']}; "
                          f"{len(d['reads'])} READ row(s) and the {d['scan']['files']}-module "
                          f"scan reproduce")
    return v


def gate_check(tool, rom, lst, built_after, *, expect_game=None, expect_debug=None,
               out=None):
    """A gate's `--built-after` path, in one call: print the verdict in the one wording,
    and return None when fresh or UNMEASURABLE (2) when not. Every migrated gate calls
    this, so no gate owns a freshness rule or a stale exit code of its own."""
    v = check_pair(rom, lst, built_after=built_after, expect_game=expect_game,
                   expect_debug=expect_debug)
    print(v.render(tool), file=out or sys.stdout, flush=True)
    return None if v.fresh else UNMEASURABLE


def pair_of(artifact):
    """The (.bin, .lst) pair an artifact name belongs to: a .bin is vouched for by its
    listing, so either half's freshness is the pair's."""
    stem, ext = os.path.splitext(artifact)
    if ext not in (".bin", ".lst"):
        raise ValueError(f"{artifact} is neither a .bin nor a .lst")
    return stem + ".bin", stem + ".lst"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rom", required=True)
    ap.add_argument("--lst", required=True)
    ap.add_argument("--built-after", type=float, default=None, metavar="EPOCH",
                    help="both files must also be written at or after EPOCH")
    ap.add_argument("--root", default=None, help="the aeon root (default: this tree)")
    ap.add_argument("--game", default=None)
    ap.add_argument("--debug", choices=("0", "1"), default=None)
    a = ap.parse_args(argv)
    v = check_pair(a.rom, a.lst, built_after=a.built_after, root=a.root,
                   expect_game=a.game,
                   expect_debug=None if a.debug is None else a.debug == "1")
    print(v.render("artifact_provenance"))
    return v.code


if __name__ == "__main__":
    sys.exit(main())
