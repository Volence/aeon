#!/usr/bin/env python3
r"""count_dashes.py — count U+2014 (em) and U+2013 (en) with ONE instrument.

WHY THIS EXISTS AS A COMMITTED TOOL RATHER THAN A ONE-LINER. Sigil's own em-dash
landing (2026-09-05) desynchronised a hand-rolled counter on a char literal and
reported 582, then 595; the true before-count was 1,031, settled only by a
SECOND independent counter run over the BEFORE tree agreeing with the agent's.
Their rule, adopted here: count before and after with the SAME instrument,
expect large-then-zero, and treat a lone after-run of zero as UNVERIFIED.

AND MY FIRST ATTEMPT AT THE BEFORE-COUNT WAS ITSELF WRONG, which is why the
instrument is a committed file and not a shell pipeline. `grep -rohP
'[\x{2014}\x{2013}]'` reported 5,007,443 occurrences — about 900k in .emp alone,
roughly 4,600 per file. Without a UTF-8 locale, PCRE does not read \x{2014} as
that code point, so the pattern matched bytes rather than characters. It
produced a confident, precise, absurd number. Python decoding each file as
UTF-8 and calling str.count is the instrument; it cannot drift on a locale.

SCOPE NOTE, stated because the number alone invites a wrong reading: this counts
ALL occurrences, including prose in docs and comments. The owner's rule covers
every string a person reads, and the docs/lane-logs clause makes the wide count
the right default. A string-literal-only count needs a per-language lexer, and a
lexer is exactly what desynchronised on sigil's char literal.
"""
import argparse, collections, pathlib, sys

EXTS = {'.emp', '.py', '.sh', '.md', '.toml', '.json'}
EM, EN = '—', '–'


def scan(root: pathlib.Path):
    per = collections.Counter()
    files = collections.Counter()
    em = en = 0
    for p in sorted(root.rglob('*')):
        if not p.is_file() or p.suffix not in EXTS:
            continue
        s = str(p)
        if '/worktrees/' in s or '/.git/' in s:
            continue
        try:
            t = p.read_text(encoding='utf-8')
        except (UnicodeDecodeError, OSError):
            continue
        a, b = t.count(EM), t.count(EN)
        if a or b:
            per[p.suffix] += a + b
            files[p.suffix] += 1
            em += a
            en += b
    return per, files, em, en


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default='.')
    ap.add_argument('--gate', action='store_true',
                    help='exit 1 if any occurrence remains')
    a = ap.parse_args()
    per, files, em, en = scan(pathlib.Path(a.root))
    for ext in sorted(per, key=lambda e: -per[e]):
        print(f"  {ext:<6} {files[ext]:4} files  {per[ext]:6} occurrences")
    total = em + en
    print(f"\n  TOTAL  em {em}  en {en}  = {total}")
    if a.gate and total:
        print(f"\nFAIL: {total} em/en dash(es) remain.", file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
