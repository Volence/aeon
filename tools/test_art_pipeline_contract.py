"""`docs/ART_PIPELINE_CONTRACT.md` must not restate a VRAM figure that has moved.

WHY THIS EXISTS, and it is a measured defect rather than a precaution.

`tools/test_bg_emit.py::TestTheContractStatesLiveValues` gates exactly ONE document,
`tools/EFFECTS_CONSUMER_CONTRACT.md`, because that is the one aurora vendors. It was
written on 2026-09-08 after that file carried a 72-tile-stale `BG_TILE_CAPACITY` for its
entire life.

`docs/ART_PIPELINE_CONTRACT.md` was not covered, and it went stale in the SAME WEEK, on
the SAME CONSTANT, from the SAME carve. Measured 2026-09-15 over master `f9413014`:

  * `BG_TILE_CAPACITY` stated as 400 at four sites; live 376.
  * `band_reserve` stated as 80 at two sites; live 56.
  * a derived `BG_TILE_CAPACITY * 32 = 12 800`; live 12 032.
  * section 2.2's VRAM map table: the TILE column was updated by the 2026-09-07 spring
    carve and the BYTE column was not, so three rows described a 380-tile BG arena
    (`$8000`-`$AF7F`) while their own tile ranges described a 376-tile one.
  * that table's own caption says "byte address = tile x 32" -- the document contained
    the rule that falsifies its own numbers, and nothing applied it.
  * the quoted `gen_vram_map` success line said "22 regions"; there are 23, and the
    23rd (`spring`) was already listed in the table three lines above the quote.

A GATE SCOPED TO ONE FILE LEAVES EVERY UNSCOPED FILE EXACTLY AS EXPOSED AS THE GATED ONE
WAS BEFORE THE GATE. That is the whole argument for this file.

WHY THE TABLE CHECK IS THE VALUABLE HALF. The constant-restatement check (below) is the
same shape as the existing gate and catches the same thing. The TABLE check catches what
the existing gate's shape cannot see at all: a figure that is not written beside the name
of the constant it came from. `$AF7F` names nothing. It is a DERIVED number, and a derived
number drifts silently precisely because it does not look like a restatement -- nobody
greps for it when the constant moves. Both stale byte columns and the stale `12 800` are
of that kind, and four of the six sites the existing gate's predicate would have found
were already fixed by hand before anyone noticed the derived ones.

LOUD ON UNMEASURABLE. Both checks assert a floor on how much they matched. A predicate
broken by a reformat matches nothing, and "matched nothing" is indistinguishable from
"the document is clean" -- which is this gate's own failure mode wearing its own hat.

EXPECTATIONS ARE DERIVED, NEVER PINNED. Nothing in this file hard-codes 376, 56, 320,
1024, $AEFF or 23. Every expected value is computed from `tools/vram_map.py` (itself
GENERATED from `games/sonic4/vram.toml` by `tools/gen_vram_map.py`) or from
`games/demo/vram.toml` through the generator's own loader. Copying a number here would
reproduce the defect one layer down.

RUNNER: `pytest tools -m "not needs_build"`, build.sh's PRE-BUILD tool-suite lane. It
reads no build artifact, so it carries no `needs_build` marker and must never acquire one.
"""

import importlib.util
import io
import os
import re
import sys
import unittest

_TOOLS = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_TOOLS)
_DOC = os.path.join(_ROOT, 'docs', 'ART_PIPELINE_CONTRACT.md')

sys.path.insert(0, _TOOLS)
import vram_map  # noqa: E402  (the GENERATED mirror; the authority for this file)


def _doc_text():
    with io.open(_DOC, encoding='utf-8') as f:
        return f.read()


def _gen_vram_map():
    """Import the generator as a module so we can call its loader without a subprocess.

    We call `load()`/`verify()` rather than shelling out because the generator's main()
    WRITES its three artifacts; this test must not mutate the tree it audits.
    """
    spec = importlib.util.spec_from_file_location(
        'gen_vram_map_for_contract_test', os.path.join(_TOOLS, 'gen_vram_map.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


#: En dash. Every range in the document's table is written with it, not a hyphen.
_DASH = '–'


def _tile_to_bytes(base, tiles):
    """Inclusive byte range of a tile run, by the table's OWN stated rule (tile x 32)."""
    return '$%04X' % (base * 32), '$%04X' % ((base + tiles - 1) * 32 + 31)


class TestTheVramTableMatchesTheGeneratedMap(unittest.TestCase):
    """Section 2.2's table is a hand-written copy of a GENERATED map. Diff them.

    The table carries, per row, a tile range and (for some rows) a byte range. Both are
    derivable from `vram_map.REGIONS`, so neither is allowed to be typed and forgotten.
    """

    #: Every row of the table must name a region the mirror knows, or be the FREE row.
    ROW = re.compile(r'^\|\s*([^|]+?)\s*\|\s*([^|]*?)\s*\|\s*([^|]+?)\s*\|')

    #: Measured 2026-09-15: 23 region rows + 1 FREE row. A FLOOR, not a pin -- adding a
    #: region must not have to touch this file. It exists so a predicate broken by a
    #: reformat fails loudly instead of vacuously. Derived, not copied: the mirror's own
    #: region count is the floor, so this cannot drift below the map.
    @property
    def MIN_ROWS(self):
        return len(vram_map.REGIONS)

    def _rows(self):
        rows = []
        for i, line in enumerate(_doc_text().split('\n'), 1):
            mo = self.ROW.match(line)
            if not mo:
                continue
            tiles, byts, name = (c.replace('`', '').replace('*', '').strip()
                                 for c in mo.groups())
            if name not in vram_map.REGIONS:
                continue
            rows.append((i, name, tiles, byts))
        return rows

    def test_every_table_row_matches_the_generated_map(self):
        rows = self._rows()
        self.assertGreaterEqual(
            len(rows), self.MIN_ROWS,
            f'the row predicate matched only {len(rows)} of the map\'s '
            f'{len(vram_map.REGIONS)} regions in {os.path.relpath(_DOC, _ROOT)}. A '
            f'predicate that matches nothing reads exactly like a clean table. Fix the '
            f'predicate, or the table really has lost rows -- do NOT lower this floor.')
        wrong = []
        for line, name, tiles, byts in rows:
            r = vram_map.REGIONS[name]
            want_tiles = (f'{r["base"]}{_DASH}{r["base"] + r["tiles"] - 1}'
                          if r['tiles'] > 1 else str(r['base']))
            if tiles != want_tiles:
                wrong.append(f'ART_PIPELINE_CONTRACT.md:{line}: {name} tile range is '
                             f'"{tiles}", the generated map says "{want_tiles}"')
            if byts:
                b0, b1 = _tile_to_bytes(r['base'], r['tiles'])
                if byts != f'{b0}{_DASH}{b1}':
                    wrong.append(
                        f'ART_PIPELINE_CONTRACT.md:{line}: {name} byte range is '
                        f'"{byts}", but the table\'s own rule (byte address = tile x 32) '
                        f'applied to the generated map gives "{b0}{_DASH}{b1}"')
        self.assertEqual(
            wrong, [],
            "section 2.2's VRAM table disagrees with tools/vram_map.py, which is "
            'GENERATED from games/sonic4/vram.toml and is the placement authority. The '
            'byte column is the one that rots unnoticed: it names no constant, so moving '
            'a region does not make anyone grep for it. Fix the prose, not this test:\n  '
            + '\n  '.join(wrong))

    def test_the_table_lists_every_region_the_map_declares(self):
        """A region added to vram.toml and not to the doc is a silent omission.

        This is the half a value-by-value check cannot catch: a MISSING row has no wrong
        number in it. `spring` was added on 2026-09-07 and the table did get its row --
        but the sentence quoting the region COUNT three lines below did not, and stayed
        at 22 for a week.
        """
        listed = {name for _, name, _, _ in self._rows()}
        missing = sorted(set(vram_map.REGIONS) - listed)
        self.assertEqual(
            missing, [],
            'games/sonic4/vram.toml declares regions that section 2.2 of '
            'docs/ART_PIPELINE_CONTRACT.md does not list: ' + ', '.join(missing) +
            '. Add the row (tiles, bytes, kind, owner) -- a map the document silently '
            'omits a region from is worse than one that states it wrongly, because '
            'nothing about the page looks incomplete.')


class TestTheContractQuotesTheGeneratorsRealOutput(unittest.TestCase):
    """The document quotes `gen_vram_map`'s success line verbatim for BOTH games.

    Re-derived by executing the generator's own `load()`/`verify()`, so the expectation
    comes from the generator rather than from a number typed here.
    """

    LINE = re.compile(r'gen_vram_map: (sonic4|demo) OK — (\d+) regions, (\d+) free tiles')

    def test_both_quoted_success_lines_are_what_the_generator_emits(self):
        text = _doc_text()
        gen = _gen_vram_map()
        live = {}
        for game in ('sonic4', 'demo'):
            regions, frees = gen.load(os.path.join(_ROOT, 'games', game, 'vram.toml'))
            gen.verify(regions, frees)
            live[game] = (len(regions), sum(f['tiles'] for f in frees), len(frees))

        hits = [(text.count('\n', 0, mo.start()) + 1, mo.group(1),
                 int(mo.group(2)), int(mo.group(3)))
                for mo in self.LINE.finditer(text)]
        self.assertGreaterEqual(
            len(hits), 2,
            f'the predicate found {len(hits)} quoted gen_vram_map success line(s); both '
            f'games were quoted when this was written. A predicate that matches nothing '
            f'reads like a clean document -- fix the predicate, not this floor.')
        wrong = []
        for line, game, regions, free in hits:
            want_r, want_f, _ = live[game]
            if (regions, free) != (want_r, want_f):
                wrong.append(f'ART_PIPELINE_CONTRACT.md:{line}: quotes "{game} OK - '
                             f'{regions} regions, {free} free tiles"; the generator '
                             f'emits {want_r} regions, {want_f} free tiles')
        self.assertEqual(
            wrong, [], 'the document quotes gen_vram_map output that the generator no '
            'longer produces. Re-run it and paste the real line:\n  ' + '\n  '.join(wrong))

    def test_the_demo_free_run_count_matches(self):
        """The TOTAL was right and the COUNT was wrong, which is why it survived a week.

        163 free tiles across 5 `[[free]]` runs was written as "4 runs totalling 163".
        A correct aggregate is not evidence for its constituents.
        """
        text = _doc_text()
        gen = _gen_vram_map()
        _, frees = gen.load(os.path.join(_ROOT, 'games', 'demo', 'vram.toml'))
        mo = re.search(r'declares (\d+) `\[\[free\]\]` runs', text)
        self.assertIsNotNone(
            mo, 'the sentence stating demo\'s `[[free]]` run count is gone from '
                'docs/ART_PIPELINE_CONTRACT.md, or was reworded past this predicate. '
                'Re-point the predicate; do not delete the check.')
        self.assertEqual(
            int(mo.group(1)), len(frees),
            f'the document says demo declares {mo.group(1)} [[free]] runs; '
            f'games/demo/vram.toml declares {len(frees)}.')


class TestTheContractStatesLiveBudgetConstants(unittest.TestCase):
    """Every budget constant the document restates beside its NAME must be the live one.

    Sibling of `test_bg_emit.py::TestTheContractStatesLiveValues`, pointed at the other
    document and at the generated mirror instead of at `inject_editor_bg`.

    SCOPE IS HONEST AND NARROW. `vram_map.py` is the only source consulted, so this covers
    the VRAM/BG budget family and nothing else. The document restates constants from
    `engine/system/constants.emp`, `engine/objects/dplc.emp` and `engine/effects/raster.emp`
    too; those were checked BY HAND on 2026-09-15 and all agreed, but they are NOT gated
    here and this docstring says so rather than letting the file's existence imply coverage
    it does not have.
    """

    #: `NAME` followed by the value the document states for it. Three spellings, ENUMERATED
    #: FROM THE FILE rather than assumed: `NAME = 376`, a table cell `NAME` | 376`, and a
    #: parenthetical `NAME` (376, ...)`. Anchored immediately after the name so that a
    #: DERIVED expression (`BG_TILE_CAPACITY * 32 = 12 032`) is deliberately NOT matched --
    #: the table check above is what covers derived figures.
    STATED = re.compile(r'`?\s*(?:=|\||\(\s*=?\s*)\s*(\d[\d,]*)\b')

    #: Measured 2026-09-15: 4 sites across 3 constants, after this session's fixes. A
    #: FLOOR, not a pin.
    MIN_SITES = 3

    def test_every_restated_budget_constant_matches_the_mirror(self):
        text = _doc_text()
        live = {n: getattr(vram_map, n) for n in dir(vram_map)
                if n.isupper() and type(getattr(vram_map, n)) is int}
        sites, wrong = [], []
        for name, value in sorted(live.items()):
            for mo in re.finditer(r'\b' + name + r'\b', text):
                hit = self.STATED.match(text[mo.end():mo.end() + 30])
                if not hit:
                    continue
                stated = int(hit.group(1).replace(',', ''))
                line = text.count('\n', 0, mo.start()) + 1
                sites.append((name, line))
                if stated != value:
                    wrong.append(f'ART_PIPELINE_CONTRACT.md:{line}: the document states '
                                 f'{name} = {stated}, the live value is {value}')
        self.assertGreaterEqual(
            len(sites), self.MIN_SITES,
            f'the predicate found only {len(sites)} restated budget constant(s) in '
            f'docs/ART_PIPELINE_CONTRACT.md; it found 4 when written. A predicate that '
            f'matches nothing reads like a clean document -- fix the predicate, do NOT '
            f'lower MIN_SITES, unless the restatements really were removed.')
        self.assertEqual(
            wrong, [],
            'docs/ART_PIPELINE_CONTRACT.md restates a budget constant that has since '
            'moved. This document is what an asset producer reads before authoring art, '
            'so a stale ceiling in it fails PERMISSIVELY -- the author meets the real '
            'ceiling as a failed BUILD. Fix the prose, not this test:\n  '
            + '\n  '.join(wrong))


if __name__ == '__main__':
    unittest.main()
