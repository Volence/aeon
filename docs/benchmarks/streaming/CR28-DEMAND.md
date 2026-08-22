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

## Adjudicated 2026-08-21 — ADOPT WITH CHANGES, accepted

Oracle ruling `docs/2026-08-21-ruling-cr28.md` (their `52ddf03`). The tuple GREW (undivided
cycle partners folded in so both normative sums gate with `==`); per-edge stall stays BARRED.
The one departure from this anchor: `entryKind` is `"hint" | "vint" | "root" | "depthCap"`
— finer than the requested `"interrupt"`, joined to the profiler's cause-keyed bucket
naming. **Accepted by the demand side**: it honours and exceeds the stated floor, and the
VBlank-entered-vs-HBlank-entered distinction is precisely what the streaming consumer
branches on. This anchor stands as history; the ruling governs the shape.

## SHIPPED 2026-08-21 — ship notice received (transcription; firsthand verification pending)

Ship notice from the oracle session, evening 2026-08-21. All SHAs on the remotes:

- **oracle main `a621e4c`** — `set_profiler{callers:true}` arming; `get_profiler_frames{topCallers}`
  (refused above `initialize.limits.maxProfilerCallers`, never clamped; `-32005 callersNotArmed`
  when unarmed); per-row `callers[]` ordered by cycles descending with flat companions
  `callersTotal`/`callersReturned`/`callersTruncated`. Edge tuple `{callerAddr?, callerName?,
  callerDisp?, entryKind?, cycles, cyclesSelf, calls, callsTotal, cyclesTotal, cyclesSelfTotal}`;
  both normative sums exact `==` when untruncated (wire-tested their side). `entryKind` is
  `"hint"|"vint"|"root"|"depthCap"`, required exactly when `callerAddr` absent. Unarmed replies
  byte-identical to pre-CR-28. Their gates: 48 legs / 1770 / 0 / 4.
- **empyrean main `70c7bb4`** — §11.18 normative text (+ amended §11.16 bound, §2.4 flat-spelling).
- **oracle-old `d629771`** (local) — MCP tool rows for the same lens; long-lived MCP server
  processes need a restart to see it.

**Caveat, theirs, honest:** `entryKind:"depthCap"` is structurally unreachable from the current
accumulator (push refuses only AT the cap; latch clears on pop) — schema-tested, never emitted
today. Booked as a known caveat, NOT a follow-up ask: our consumer branches on hint/vint/root.

**What we still owe:** firsthand consumption — arm callers on the fill/S4LZ rows from a live
probe, check `topCallers` refusal, both `==` sums, and the hint-vs-vint split against ground
truth. First natural consumer: the staging-lifetime settling probe (TICK-VARIANCE §3 successor).
Until that runs, everything above is transcription, not verification.
