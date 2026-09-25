#!/usr/bin/env python3
"""Passive per-thread CPU of a running process from /proc (read-only; sends nothing to it).
Usage: thread_cpu.py <pid> <seconds>"""
import os
import sys
import time

pid, secs = int(sys.argv[1]), float(sys.argv[2])
hz = os.sysconf("SC_CLK_TCK")


def snap():
    out = {}
    for t in os.listdir(f"/proc/{pid}/task"):
        try:
            st = open(f"/proc/{pid}/task/{t}/stat").read()
            comm = open(f"/proc/{pid}/task/{t}/comm").read().strip()
        except OSError:
            continue
        f = st[st.rindex(")") + 2:].split()
        out[t] = (comm, int(f[11]) + int(f[12]), f[0])
    return out


a = snap()
t0 = time.monotonic()
time.sleep(secs)
b = snap()
dt = time.monotonic() - t0
print(f"pid {pid} window {dt:.2f}s loadavg {open('/proc/loadavg').read().strip()} "
      f"utc {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}")
tot = 0.0
for t in sorted(b, key=lambda t: -(b[t][1] - a.get(t, (0, b[t][1]))[1])):
    d = (b[t][1] - a.get(t, (0, b[t][1]))[1]) / hz / dt * 100
    tot += d
    print(f"  tid {t:>8} {b[t][0]:<20} state {b[t][2]} cpu {d:6.1f}%")
print(f"  total {tot:.1f}% of one core")
