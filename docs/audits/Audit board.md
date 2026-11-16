---
kind: board
status: reference
cssclasses:
  - wide
description: "Every system audit across the suite: waves, status, and where each one stands."
---
# Audit board

Started 2026-11-16. Each system is judged against the best known approach and the hardware limit by
independent agents, merged by a Fable lead. Shape of every audit: [[AUDIT_TEMPLATE]] (v2). Why: 
[[2026-11-16-engine-quality-process-changes]]. How the pilot went and what changed: [[Audit process review]].

![[Audits.base#All audits]]

## Owner direction (2026-11-16)

- **Starting over the correct way is allowed.** No rush. Systems an audit marks *rewrite beside* get written
  fresh, natively, beside the old engine, with the old ROM as the behaviour reference. A full restart is
  reconsidered after the foundation audits, against the four conditions in [[Audit process review]].
- **The `.emp` language itself is open.** It may become less assembly-like, even functional, if that serves
  the engine and games better. The language audit weighs this, starting from
  [[SIGIL_IDEAS_FUNCTIONAL_TIER]].
- **Owner question for the EMP language audit (added mid-run, 2026-11-16): should the functional
  language cover EVERYTHING, not just game logic?** That means the engine too, including VBlank/HBlank,
  DMA, the decompressors, the sound driver and the hot inner loops, with exact instructions available
  only as an escape hatch (like inline asm) or not at all. Research, both reviewers, the checker and
  the lead must each treat "functional everywhere" as its own option, beside "functional for logic,
  exact for hot paths". For each engine area, give the evidence: what a compiler can and cannot
  match on a 68000 (cycle-exact interrupt code, Z80 bus timing, DMA windows), the estimated
  cycle/byte cost against today's code, and what the escape hatch would have to look like. The lead
  answers the question plainly on the audit page.

## Waves

| Wave | Audits | State |
|---|---|---|
| 0 (pilot) | [[Frame architecture]] | 🟠 done, awaiting your decisions; its tick-logic-order half moves to wave 2 |
| 1 (tools) | [[EMP language]], [[Sigil assembler]], [[Oracle fitness]] (fitness check: accurate enough to judge what the engine audits need?) | 🔵 |
| Before wave 2 | One-off harness fix: stress shape with objects + sidekick, streaming act, PAL boot, working run leg, release top-speed leg, VBlank-end probe, pinned emulator build | 💡 |
| 2 (foundation) | Engine/game contract, Level data format, Tile streaming + art pool + compression, Tick logic order + collision + physics | 💡 |
| 3 | Object system + object interaction, Sprite drawing, VRAM layout + DMA queue, RAM map | 💡 |
| 4 | Camera, Background + effects, Sound driver, Input + replay, Boot + VDP, Debug tooling, Level bake tools + build gates | 💡 |
| Design reviews | Game modes, HUD + text, Saves, Character select + sidekick AI, Water, Lives + game over | 💡 lighter shape, in vertical-slice order |

**Shared budgets have one owning audit:** the per-frame DMA/VBlank budget belongs to *VRAM layout + DMA
queue*; the object loop's cost belongs to *Object system*; parallax belongs to *Background + effects*.
Other audits cite the owner rather than re-deriving it.

## How to follow an audit

Open the system's page. Its **Stages** table shows which agent is working; each finished stage links its
raw report. The merged verdict, findings and at most five decisions land at the top when the lead finishes.
