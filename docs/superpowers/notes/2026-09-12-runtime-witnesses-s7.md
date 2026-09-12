# Runtime witnesses, 2026-09-12 seventh aeon session (controller, emulator)

ROM: /home/volence/sonic_hacks/.aeon-ls8-land/s4.debug.bin at c5dd8c20 (847533 B, crc32 b93a889f), symbols s4.debug.lst
from the same tree (binding "match"). Oracle own-instance server pid 510366 (was holding .aeon-probes/c3b3; reloaded).
Boot lands in GameState_OJZScroll_Update (the OJZ scroll test: input free-scrolls, 16 px/frame, no player physics).

## C1b-3 — cache origin stays even (premise of floor((L+O)/2))
Checkpoint at frame 400; write watchpoint on Cache_Origin_Row ($FFAE58); play_input down [0,150) up [150,300).
289 writes, frames 403..699, truncated=false, dropped=0. 0 odd values. Every step exactly +/-2 mod 60 (0 exceptions),
wraps 58->0 seen. Writers: TileCache_VSlide.vslide_nowrap 146, TileCache_VSlideUp.vsu_nowrap 143 (size 2 each).
Final 6 = 3 net down-slides (146-143) x 2. Camera_Y $00C0 at frame 700.
LIMIT: the scroll test has no physics, so Collision_GetType itself was not exercised at a non-zero origin; the
equivalence is the C1b-3 parcel's exhaustive byte check. This witnesses the PREMISE only.

## EFX-4b — Raster_Buf_A zero past terminator (PARTIAL)
Frame 400 after boot: 30 bytes of program ending 8AFF FFFF, then zeros through byte 128. First install only;
the longer->shorter re-install case (what the padding exists for) not yet observed.

## C4a-4 — every tracked entry's ess_section_id unchanged in meaning across a slide (now from GetSecPtrXY's d0)
Expected id derived independently from each entry's own stored origin: (origin_y>>11)*GRID_W + (origin_x>>11),
GRID_W=3 (act_descriptor.emp), SECTION_SIZE_SHIFT=11. Entity_Scan_State = 4 x $1A.
Before (frame 400, restored checkpoint; bases OriginX/Y 0/0; Camera_X $0060): origins (0,0)(2048,0)(0,2048)(2048,2048)
-> ids 0,1,3,4, all match. Held right 200 frames -> frame 600: Entity_Window_OriginX $0800, Camera_X $0CA0; all four
entries rewritten: (2048,0)(4096,0)(2048,2048)(4096,2048) -> ids 1,2,4,5, all match expected.
Then held down 200 frames -> frame 800: bases $0800/$0800, Camera_Y $0CD0; entries (2048,2048)(4096,2048)(2048,4096)
(4096,4096) -> ids 4,5,7,8, all match. Row 2 (sec_y*GRID_W = 6) exercised. VERDICT: witnessed, both axes.

## C4a-2 — the same rings spawn after a slide away and back (SPAWN HALF witnessed; collected half unreachable here)
Frame 400 (checkpoint): Ring_Count 7, all section 0, list idx 0-6 at (128,96)(144,96)(160,96)(176,96)(192,96)(308,157)
(324,157). Held right 200 then left 200 -> frame 800, Camera_X $0070: Ring_Count 13, HighWater 21. All seven section-0
rings back, same list indices and positions (buffer order differs); the six others are section 1 idx 0-5
(x $0900-$0A00, y $40-$60), kept by design: EntityWindow_DespawnRings' header, X-despawn is skipped for rings whose
section is an active window entry, and section 1 is in the 2x2 window. Despawn mid-trip not captured directly; the
identical first 200 frames from the same checkpoint put the window at cols 1-2 with no section 0 entry (C4a-4 run).
Collected half: the scroll test has no player physics, so nothing can be collected; not witnessed.

## Draw_Sprite short entry (parcel/draw-sprite-short-entry, fix 02736b9f) — runtime, on the BRANCH ROM
ROM: agent worktree s4.debug.bin crc32 9ce1c2ff / 847533 (listing bound "match"). Frame 400 boot:
screenshot identical to master's frame 400 (player box + two rings; PNG 32658 B both). Camera (96,144).
render_flags (+$0E): Player_1 $81 (ONSCREEN set, drawn); all six springs (y 478..584, below the screen) $60/$60/$64/
$62/$60/$60, ONSCREEN clear.
Then held down 22 frames -> frame 422, camera (96,448): springs x520 $60 (clear, culled past the right edge);
x440 $61, x430/y478 $65, x360 $63, x160 $61, x112 $61 (ONSCREEN set); screenshot shows the springs drawn.
CONTROL: master ROM (.aeon-ls8-land s4.debug.bin b93a889f, c5dd8c20), same boot (400 frames) + the same 22-frame
down: the six spring slots (480 B from $FF9B3E) are BYTE-IDENTICAL to the branch's, flags $60 $61 $65 $63 $61 $61;
screenshots both 39567 B, same picture. VERDICT: the move changes no ONSCREEN/cull outcome in this scene; both the
registered (drawn) and the culled paths witnessed. Not covered: a multisprite parent (none placed in OJZ act 1) and
a null-mappings object.

## Landing A (Draw_Sprite + zero-byte residue), .aeon-ls8-land, merges 468bcd1d + 9e659ef8 on c5dd8c20
Z80 clobbers gate (constants.emp moved): from .sigil-pin-6884bfba (clean, HEAD 6884bfba), CARGO_TARGET_DIR
.aeon-landing-sigil-target, SIGIL_STRICT_GATE=1, AEON_DIR=.aeon-ls8-land: rc=0, `5 passed` (file has 5 #[test]),
reference-tree names the merged tree, no skip: line. SIGIL_BUILD md5 2e7c2592... before and after (not relinked).
landing_build.sh started 11:35:39Z detached, log .runlogs/landing-0912-s7a.log. Expected CRCs = the Draw_Sprite
branch's (9cdeb9b1 / 9ce1c2ff / 3170d31e / 3cf4f104): the zero-byte parcel must add nothing.

## Not run this session (still owed, controller-only)
C4a-3 profile EntityWindow_DespawnRings at a FULL ring buffer; C2a-6 piece count $FF + wrong cached offset asserts;
B2a-2 (optional); EFX-4b the longer->shorter re-install case; C3b-2 lag-frame residue; C4a-2 collected half (needs a
state with player physics, not the scroll test).

## Killed_MarkObject — emulator look is UNREACHABLE BY CONSTRUCTION
Touch_Enemy is an rts stub (engine/objects/collision.emp, the falls_into stub chain); OJZ act 1 places no enemy
(section_0: solid + 7 springs; section_1: solid; section_2: solid + static; 3-8 empty). Nothing can be destroyed, so
an unset killed mask is correct today. Sst carries entity_section_id ($2B) and entity_list_index ($2C), so the future
enemy-defeat path has both inputs. Re-book: wire Killed_MarkObject in the parcel that gives Touch_Enemy a defeat.

## Landing A result (recorded at the land commit)
`tools/landing_build.sh .runlogs/landing-0912-s7a.log` on merge `9e659ef8` (merges `468bcd1d` Draw_Sprite short entry +
`9e659ef8` zero-byte residue, on `c5dd8c20`), started 11:35:39Z, `finished=0`. EXIT_s4/s4.debug/demo/demo.debug/needs_build
all 0. Pre-build lane 2524 passed / 2 skipped / 0 failed per shape; needs_build 14 ran / 0 deferred / 0 failed.
ROMs: s4 `9cdeb9b1` / 821155, s4.debug `9ce1c2ff` / 847533, demo `3170d31e` / 97109, demo.debug `3cf4f104` / 103501, all
written 11:39Z..11:50Z (after the start), equal to the Draw_Sprite branch's own CRCs, so the zero-byte parcel moved nothing.
Assembler `sigil` md5 `2e7c25920b95cec2c462ea51b4f078b5` (6884bfba), emitter `d258341604bbf735a8af8438c2b8d642`.
