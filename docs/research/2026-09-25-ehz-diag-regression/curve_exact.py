#!/usr/bin/env python3
"""Exhaustive: for every span 1..224 and rem 0..span-1, the shipped Bresenham carry sequence
(err += rem; if err >= span: err -= span, +1) equals the 0.16 fixed-point carry sequence
(frac = ceil(rem*65536/span); f += frac; carry out of 16 bits) on every line k = 1..224
(a continued/split layer still counts k from the layer start and never exceeds 224 lines).
MUTATION control: --floor uses floor() instead of ceil() and must report mismatches."""
import sys
floor = "--floor" in sys.argv
bad = 0; cases = 0
for span in range(1, 225):
    for rem in range(span):
        frac = (rem * 65536) // span if floor else (rem * 65536 + span - 1) // span
        assert frac < 65536
        err = 0; f = 0
        for k in range(224):
            err += rem; c1 = 0
            if err >= span:
                err -= span; c1 = 1
            f += frac; c2 = f >> 16; f &= 0xFFFF
            if c1 != c2:
                bad += 1
            cases += 1
print(f"{'floor (mutation)' if floor else 'ceil'}: cases={cases} mismatches={bad}")
