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
EM, EN = '\u2014', '\u2013'

# ESCAPED SPELLINGS. A dash written as an escape RENDERS IDENTICALLY and is
# INVISIBLE to str.count, so a character-based count cannot find it and cannot
# know it is wrong. Aurora hit this first (their sweep total was 209 and the
# truth was 210, the missing one spelled as a backslash-u escape), flagged it,
# and this counter had the same blind spot. Checking rather than assuming found
# it live in OUR OWN OUTPUT: json.dumps defaults to ensure_ascii=True, so every
# em dash this lane wrote into docs/lane-status.json -- a file the owner's
# console renders on his card -- was stored as \u2014 and counted as zero.
# These are reported SEPARATELY rather than folded into the total, because they
# are a different remediation: the character ones are edits, these are usually a
# serializer setting (pass ensure_ascii=False and they become visible).
ESCAPED = [
    r'\u2014', r'\u2013', r'\U00002014', r'\U00002013',
    '&mdash;', '&ndash;', '&#8212;', '&#8211;', '&#x2014;', '&#x2013;',
]


def scan(root: pathlib.Path):
    per = collections.Counter()
    files = collections.Counter()
    escaped = collections.Counter()
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
        low = t.lower()
        esc = sum(low.count(s.lower()) for s in ESCAPED)
        if a or b:
            per[p.suffix] += a + b
            files[p.suffix] += 1
            em += a
            en += b
        if esc:
            escaped[p.suffix] += esc
    return per, files, em, en, escaped


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default='.')
    ap.add_argument('--gate', action='store_true',
                    help='exit 1 if any occurrence remains')
    a = ap.parse_args()
    per, files, em, en, escaped = scan(pathlib.Path(a.root))
    for ext in sorted(per, key=lambda e: -per[e]):
        print(f"  {ext:<6} {files[ext]:4} files  {per[ext]:6} occurrences")
    total = em + en
    print(f"\n  TOTAL  em {em}  en {en}  = {total}")
    if escaped:
        esc_total = sum(escaped.values())
        print(f"\n  PLUS {esc_total} dash(es) spelled as an ESCAPE, which render "
              f"identically and which the count above CANNOT see:")
        for ext in sorted(escaped, key=lambda e: -escaped[e]):
            print(f"    {ext:<6} {escaped[ext]:6}")
        print("  These usually mean a serializer wrote them (json.dumps defaults to "
              "ensure_ascii=True); pass ensure_ascii=False to make them visible.")
    else:
        print("\n  No dashes spelled as escapes.")
    if a.gate and total:
        print(f"\nFAIL: {total} em/en dash(es) remain.", file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
