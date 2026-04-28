# Spec — Animation Event Tags (Research + Design)

## Context

Reading the Ristar disassembly + community research, one of the most
distinctive engine patterns we found is **inline event tags in the
animation frame stream** — each animation frame carries SFX trigger,
hitbox swap, and callback bytes alongside the frame index and duration.
This means the animation system itself drives cinematic events: no
parallel state machine polling for "frame 5 of throw anim → play SFX,"
the SFX is glued to the frame.

See `ristar_disasm/ANALYSIS.md` "Distinctive techniques" #1 and
`docs/research/ristar-techniques.md` § "Event-tagged animation frames."
The exact Ristar tag-byte layout is INFERRED — we have not yet decoded
an animation table from the ROM.

## Why we're doing this NOW

Adding event tags later is a **format break**. Every animation table
ever written has to be rewritten or dual-supported. We have *some*
animations shipped (player, test objects) but not many. Designing the
format before the next animation work means we either bake it in or
firmly decide not to — no half-measures, no migration debt.

If we decide NOT to adopt, we lock that decision in writing and stop
revisiting it.

## Goal

Produce **a research note + design recommendation** for animation
event tags. Implementation is a separate plan, opened only if the
recommendation is "adopt."

## Files in scope

**Read first:**
- `docs/research/animation-system.md` — current research baseline,
  documents how all 7 reference engines author animations
- `engine/objects/animate.asm` — current `AnimateSprite` implementation
- `ENGINE_ARCHITECTURE.md` — animation system section
- `ristar_disasm/ANALYSIS.md` — "Distinctive techniques" #1 and
  "What to look at next" item on tracing an actual animation update
  routine in Ristar

**Maybe useful (cross-engine survey):**
- S.C.E.: `Engine/Objects/Animate Sprite.asm` (control codes $FB-$FF)
- Sonic 3K disasm — same control-code pattern as S.C.E.
- Treasure (Gunstar/Alien Soldier) `disasm.asm` — animation update
  routines often have inline timer + jump dispatch
- Vectorman — pre-rendered frames, less applicable but worth a glance
- Modern engines — Unity AnimationEvents, Godot's AnimationPlayer key
  tracks, Unreal's AnimNotify pattern

## Tasks

1. **Read existing animation-system research** and summarize current
   plan: what does our animation script format look like today? Frame
   format, control codes, lookup path.

2. **Survey reference engines** for event-tag patterns. Look for:
   - SFX triggers
   - Hitbox / collision-rect swaps
   - Damage/hurtbox window enable/disable
   - Custom callback / jump-to-routine
   - Spawn dust / particle / projectile from frame
   - Decoration (palette flash, screen shake, hit-stop)
   Document how each engine encodes these. Ristar specifically: trace
   an animation update routine in `ristar_disasm/code/disasm.asm` (find
   any routine that reads `anim_frame` SST offset; decode the table format
   from what it parses).

3. **Compare format options.** At least 3 candidates:
   - **Inline byte tags** (like Sonic 3K control codes $FB-$FF
     extended): each frame entry is `(frame_index, duration, tag_byte,
     tag_arg)` — 4 bytes per frame, tag = 0 means no event.
   - **Sentinel-extended frames**: variable-length per-frame entry with
     a flag bit indicating "extra event data follows"; cheaper for
     no-event frames, more parser work.
   - **Parallel tag stream**: frames stay (frame_index, duration), with
     a separate per-animation `events` table indexed by frame number.
     No per-frame cost; second lookup per frame.
   - **None — keep current**: parallel state machine in object code
     polls anim_frame, fires events from the obj-side. Cost: every
     animated object that wants SFX needs custom polling code.

4. **Cost analysis for each option.**
   - Bytes per frame entry (RAM cost is zero — these live in ROM)
   - Cycles per frame to parse + dispatch tag
   - Format extension headroom (how easy to add a new event type later)
   - Authoring ergonomics (how hard for the level/anim author to write)

5. **Recommend ONE option with justification.** Or recommend "skip"
   with justification.

6. **If recommendation is "adopt":** propose the exact bit/byte layout
   of the chosen format, the dispatch code shape (~20 lines of 68k),
   and a list of event types we want on day one (suggested minimum:
   SFX, callback, no-op-pad).

7. **If recommendation is "skip":** document the reasoning so we don't
   reopen this decision in 3 months.

## Deliverable

Single new file: `docs/research/animation-event-tags-§3.md` (or
similar — match existing animation-system naming).

Structure:
- Per-engine survey (4-6 references)
- Format options + cost table
- Recommendation
- (If adopt) format spec ready to be implemented

If the recommendation is "adopt," update `docs/research/animation-system.md`
and `ENGINE_ARCHITECTURE.md` to reflect the new format; open a separate
implementation plan for the actual code change.

## Acceptance criteria

- [ ] Research note exists with cross-engine survey.
- [ ] Format options compared in a cost table.
- [ ] Single recommendation (adopt format X, or skip).
- [ ] If adopt: format byte layout is concrete enough to implement
  without further design questions.
- [ ] If skip: rationale is durable enough to prevent re-litigating.

## Notes

- This is RESEARCH + DESIGN, not implementation. Do not write engine
  code. Update animation-system docs only with the design decision,
  not with a new implementation.
- Time estimate: half a day to research, half a day to write the note.
- Resist the urge to design beyond minimum. SFX + callback + pad is
  enough for v1. Hitbox swap, dust spawn, etc. are all adoptable later
  via the callback escape hatch — we just need the *plumbing* in place.
