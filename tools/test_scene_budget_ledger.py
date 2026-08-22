#!/usr/bin/env python3
"""The scene-budget ledger's required-rows list stays true to the source (P3 Task 14).

scene_budget_report.py's LEDGER_ROWS is the readback contract: `--check` fails when a
published row is missing from the listing. But `--check` needs a built artifact and so
cannot run in the canonical build's tool sweep — which left the LIST itself with no
runner: a row renamed or dropped on either side (the registry's `pub equ` or the tool's
LEDGER_ROWS) would regress SILENTLY, the report simply rendering less. This suite is the
runner (build.sh's pytest lane, canonical shapes), and it gates at the SOURCE level:

  * every LEDGER_ROWS name must exist as a `pub equ` in the registry module, and
  * every `pub equ SceneBudget_*` in the registry must be listed in LEDGER_ROWS, and
  * the rows must be spelled `pub equ`, never `pub const` — a const mints no symbol,
    so the artifact-side `--check` would fail loudly, but only after someone ran it.

Expectations are DERIVED by parsing the registry source; no row name is duplicated here.
What this cannot see — sigil ceasing to emit equates to the listing at all — remains
`--check`'s job against a DEBUG listing (run it after any sigil listing-format change).

Red-first (P3 Task 14, both directions, restored): a row deleted from LEDGER_ROWS failed
`test_every_registry_row_is_required`; a registry equ renamed failed
`test_every_required_row_is_published`.
"""

import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scene_budget_report import LEDGER_ROWS  # noqa: E402

AEON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRY = os.path.join(AEON, "games", "sonic4", "data", "effects", "scene_registry.emp")

# `pub equ Name = <expr>` — the ledger-row spelling. Anchored to line start (after
# indentation) so a comment mentioning `pub equ` cannot match.
PUB_EQU_RE = re.compile(r"^\s*pub\s+equ\s+(SceneBudget_[A-Za-z0-9_]+)\s*=", re.M)
# The anti-pattern: a SceneBudget_* row spelled `pub const` mints no listing symbol.
PUB_CONST_RE = re.compile(r"^\s*pub\s+const\s+(SceneBudget_[A-Za-z0-9_]+)\s*=", re.M)


def strip_line_comments(src: str) -> str:
    """Drop // line comments so a commented-out row is neither published nor required."""
    return "\n".join(line.split("//", 1)[0] for line in src.split("\n"))


class TestLedgerRowSync(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(REGISTRY, "r", encoding="utf-8") as fh:
            cls.src = strip_line_comments(fh.read())
        cls.published = PUB_EQU_RE.findall(cls.src)

    def test_registry_module_exists(self):
        self.assertTrue(os.path.isfile(REGISTRY), REGISTRY)

    def test_every_required_row_is_published(self):
        missing = [r for r in LEDGER_ROWS if r not in self.published]
        self.assertEqual(missing, [],
                         f"LEDGER_ROWS names rows the registry no longer publishes as "
                         f"pub equ: {missing} — the artifact-side --check would fail; "
                         f"fix the registry or retire the row in BOTH places")

    def test_every_registry_row_is_required(self):
        unlisted = [r for r in self.published if r not in LEDGER_ROWS]
        self.assertEqual(unlisted, [],
                         f"registry publishes ledger rows LEDGER_ROWS does not require: "
                         f"{unlisted} — an unlisted row can vanish from the listing "
                         f"with no gate noticing; add it to scene_budget_report.py")

    def test_no_ledger_row_is_pub_const(self):
        consts = PUB_CONST_RE.findall(self.src)
        self.assertEqual(consts, [],
                         f"SceneBudget_* rows spelled pub const (mints NO symbol — the "
                         f"formatter cannot see it): {consts}")

    def test_no_duplicate_required_rows(self):
        dupes = sorted({r for r in LEDGER_ROWS if LEDGER_ROWS.count(r) > 1})
        self.assertEqual(dupes, [])

    def test_no_duplicate_published_rows(self):
        dupes = sorted({r for r in self.published if self.published.count(r) > 1})
        self.assertEqual(dupes, [])

    def test_axis5_rows_are_present(self):
        """The Task-14 rows specifically: nine axis-5 rows, three per sub-ceiling.

        Derived from the published set rather than typed as a literal list — the
        assertion is the COUNT and triple-shape, so a legitimate axis-5 rename still
        passes the sync tests above while a silent drop of a triple fails here.
        """
        a5 = [r for r in self.published if r.startswith("SceneBudget_Axis5_")]
        self.assertEqual(len(a5), 9, a5)
        for metric in ("LineSprite", "LinePixel", "TableSlot"):
            triple = [r for r in a5 if metric in r]
            self.assertEqual(len(triple), 3,
                             f"axis-5 {metric} sub-ceiling is not a full "
                             f"max/reservation/pool triple: {triple}")


if __name__ == "__main__":
    unittest.main()
