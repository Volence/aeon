# CR-28 demand anchor — the profiler caller breakdown, aeon's answers (2026-08-21)

Aeon is the requesting customer for CR-28 (per-routine caller breakdown; our C3 streaming
ask). Oracle proposed the wire shape before building (their
`docs/2026-08-19-streaming-asks-recon.md` §4, answers relayed in
`docs/2026-08-21-cr28-shape-answer.md`); this file is the committed demand-side position.

**Workload this serves:** burst attribution for the streaming variance work — who invokes
`S4LZ_DecompressDict` / `TileCache_FindStagedBlock`, per 31-frame window, with callee
self-time attributed by caller (`TICK-VARIANCE.md`'s successor instrument).

1. **In-row `callers[]` under opt-in arming (`set_profiler{callers:true}`) — accepted.**
   The deciding reason is atomicity: the separate-method fallback has cross-read skew (two
   pure reads describe different samples → correlated figures with different divisors), the
   exact silent-wrong instrument class this suite keeps paying for. Fallback stays on
   record, unbuilt.
2. **Per-edge tuple as proposed** `{callerAddr?, callerName?, callerDisp?, cycles,
   cyclesSelf, calls, callsTotal}` — keep per-edge `callsTotal` (row symmetry), per-edge
   `cyclesSelf` is the money field. Per-edge stall explicitly DECLINED (measured flat and
   VBlank-owned at every state taken; dead weight).
3. **Absence must carry its reason:** when `callerAddr` is absent, a required
   `entryKind: "interrupt" | "root" | "depthCap"` on the edge — one absence must not mean
   three facts. Floor position if the enum spelling loses adjudication: interrupt-entered
   edges keyed distinctly from the other two, however spelled (interrupt-vs-mainline is a
   distinction the streaming consumer will actually branch on).

Also acknowledged from their recon: caller accounting is per-call not per-instruction
(our "nearly free" read verified), and a root frame's `callerAddr` may be mid-routine —
the contract text says so.
