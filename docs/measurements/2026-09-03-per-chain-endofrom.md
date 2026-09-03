# Per-chain DEBUG EndOfRom, aeon 8876459e..4f5ad5a1 — measured 2026-09-03

Produced for the sigil lane's per-chain baseline terms. Committed because it existed only in
a cross-lane message and a session-local scratchpad, neither of which survives a rotation —
the shared protocol's own bar: mail is not part of the tree, so no tree can surface a wrong
claim made in mail, and no reader can recover a right one.

## Method

Thirteen canonical `DEBUG=1 ./build.sh` runs in a dedicated worktree, EndOfRom read from each
listing. ONE assembler at every point — sigil 0a58f2ecc8e77c9433bc0ea3f0549c1e0e556f3b, md5
6c2378ae8a657e26684d4019a7d976d7 — so the deltas isolate aeon changes rather than toolchain
drift. If a baseline instead wants terms as measured by the assembler current AT each landing,
these are not those.

`CONTRACTS=0` throughout: sigil's D1c frozen baseline expects the band-drift adoption and
therefore fires on every pre-201 point BY CONSTRUCTION. It is a static analysis, not a code
transform. CONTROL: chain 208 built here gives s4.debug.bin 737683 bytes, byte-for-byte the
figure sigil's independent reference tree holds, so the hatch moved nothing.

Three rows exit non-zero and their numbers are given anyway, deliberately: a failing
post-assembly gate does not invalidate an assembled length, and suppressing the exit code
would have been the dishonest half.

## The series

```
b81e5daa  0xA7F38  736664  rc=1
c4d98897  0xA7F38  736664  rc=1
4e16155f  0xA7F38  736664  rc=0
cb0e5eb1  0xA8118  737292  rc=0
fd4ad7af  0xA8118  737292  rc=0
bbe74e4f  0xA8118  737292  rc=0
ce4dbb7c  0xA8118  737292  rc=0
36285940  0xA81FC  737629  rc=0
b294234b  0xA81FC  737643  rc=0
2344c4c3  0xA81FC  737683  rc=1
4868b912  0xA81FC  737683  rc=0
4f5ad5a1  0xA81FC  737683  rc=0
```

## Self-checks

- Endpoints match the two values sigil held independently: 0xA7F38 and 0xA81FC.
- Two non-zero terms, 0x1E0 (chain 202) + 0xE4 (chain 206) = **0x2C4**, the required span.
- Ten explicit HOLDS, each measured rather than inferred from a neighbour.

## What the series explained

Chain 208's own agent reported *"+38 for a 64-byte routine is measured, not explained; I did
not chase it."* Chains 207 and 208 moved FILE bytes (+14, +40) and moved EndOfRom by **zero** —
the loop-crossover read side landed in space that did not extend the assembled image, so the
whole file delta was deb2 appendix taking new labels. Only visible once the two quantities are
separated, which is why file deltas are not baseline terms.
