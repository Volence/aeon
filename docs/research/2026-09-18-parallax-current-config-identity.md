# `Parallax_Current_Config` holds an `EditorSceneBinding_*` — and that is CORRECT

Bounded diagnostic, 2026-09-18, branch `diag/parallax-current-config-identity` off `c92f7248`.
Measured in an own worktree (`/home/volence/sonic_hacks/aeon-wt-pcc`), own `DEBUG=1 ./build.sh`
(`s4.debug.bin` 848,075 bytes, crc32 `62238a15`). One question, no fix written.

## The question

`tools/fg_left_edge_gate.py` reads `Parallax_Current_Config` (`engine/ram.emp:490`) and was
observed holding `$01486E` = `EditorSceneBinding_OJZ_Act1_Sec0` on all six lab scenes, never
moving. `$01486E` is not one of the `ParallaxConfig_Perspective*` records whose
`pcfg_v_deform_shift_bg` carries the decline bit. Was the pointer wrong in an ORDINARY boot too
(a live, silent visual defect), or only under the gate's lab install?

## Answer: GATE ARTIFACT — and the pointer is never wrong at all

Two separate premises in the report are wrong, and correcting them dissolves the question.

### 1. `EditorSceneBinding_OJZ_Act1_Sec0` IS a `parallax_config` — it is the SAME TYPE

`games/sonic4/data/effects/scene_registry.emp:139-176` says so explicitly, and pins it:

- `pub struct SceneCfg5 { hdr: parallax_config, bands: [band_record; 5] }`
- `ParallaxConfig_Perspective_Subtle: SceneCfg5 = lower5(SCENES[13])`  (`scene_registry.emp:804`)
- `EditorSceneBinding_OJZ_Act1_Sec0: SceneCfg5 = lower5(EditorScenes_OJZ_Act1[3])`
  (`games/sonic4/data/generated/ojz/act1/effects_scenes.emp:166`)

They are both `SceneCfg5`, both 190 bytes. Sixteen `ensure(offsetof(SceneCfgN, hdr) == 0, ...)`
lines make "a pointer to the binding label is a pointer to its `parallax_config`" a build error
to break. "Same size, different struct" was the observation; the struct is the same one.

The two families differ only in PROVENANCE: `ParallaxConfig_*` are the hand-authored scene
library, referenced in this tree ONLY by `games/sonic4/test/ojz_scroll_test.emp`'s lab table and
by `scene_equiv_proof.emp`'s ensures. `EditorSceneBinding_*` are what the region table binds
(`games/sonic4/data/generated/ojz/act1/regions.emp:62-70`, `rg_parallax:`). **An ordinary boot
installs the editor bindings by design; it never installs a `ParallaxConfig_*` at all.**

### 2. An ordinary boot holds exactly the right one — measured

`tools/pcc_identity_probe.py` (added by this diagnostic; reports, asserts nothing), one
`oracle-aether` on its own socket, B pressed to leave DEBUG free flight, 240 boot frames + play +
300 frames of held RIGHT + 60 settle. Every sample:

    Current=$01486E EditorSceneBinding_OJZ_Act1_Sec0  Target=$000000 Frames=0  Region=$018B2C

`Region_Current` `$018B2C` is `OJZ_Act1_Regions + 0` — region row 0 exactly, whose `rg_parallax`
IS `EditorSceneBinding_OJZ_Act1_Sec0`. One distinct value over the run; it resolves to a config
label. The camera never left region row 0 (x 0..2047, y 0..2047), so that run witnesses one region.

The multi-region witness already exists and is green on this build: `tools/boot_override_gate.py`
**PASS**, which derives the expectation independently (`Effects_ResolveParallax` restated over
the ROM's own region table) at two ordinary boots:

    authored    region centre (256, 256)   -> 0x1486e EditorSceneBinding_OJZ_Act1_Sec0 [region row 0], seeded 0x1486e
    destination region centre (2560, 2400) -> 0x1492c EditorSceneBinding_OJZ_Act1_Sec4 [region row 4], seeded 0x1492c

### 3. What the lab does differently: it reads the cell DURING a staged transition

`tools/pcc_lab_probe.py` (added here) drives the gate's OWN `drive_cursor` and reads all three
cells:

    [boot +240f      ] Lab=  0  Current=$01486E Sec0        Target=$000000 -                     Frames=0
    [cursor -> 13 +0f] Lab= 13  Current=$01486E Sec0        Target=$013FCE Perspective_Subtle    Frames=7
    [cursor -> 13 +4f] Lab= 13  Current=$01486E Sec0        Target=$013FCE Perspective_Subtle    Frames=3
    [cursor -> 13+64f] Lab= 13  Current=$013FCE Persp_Subtle Target=$000000 -                    Frames=0
    [cursor -> 14 +0f] Lab= 14  Current=$013FCE Persp_Subtle Target=$01408C Perspective          Frames=7

The lab install WORKS. Every scene in the tree authors `pcfg_transition == 0` (smooth), so
`Parallax_StartTransition` (`engine/level/parallax.emp:1334`) takes its CAP_TRANSITIONS staging
arm — live here, `Game.SCANLINE_CAPS` `$0FDE` & `CAP_TRANSITIONS` `$0010` — which writes
`Parallax_Target_Config` and `Parallax_Transition_Frames = PARALLAX_TRANS_DEFAULT` (16) and
**deliberately leaves `Parallax_Current_Config` alone**. `Parallax_Update` promotes Target into
Current only when the counter reaches 0 (`parallax.emp:1785-1800`).

`drive_cursor`'s `step_scene` advances 8 input frames + 4 run frames = **12 frames per step**, and
a transition needs **16**. So every step re-stages before the previous promotes, `Current` never
gets a settled frame during the walk, and at the gate's sample point — taken the instant
`drive_cursor` returns — it still holds the boot's region binding. That is why it read `$01486E`
on all six scenes and "never moved": not a stuck pointer, a **9-of-16-frames-early read**.

The engine's own accessor for "which config is active THIS frame" is
`Parallax_Active_Config` (`parallax.emp:1480`): `Frames != 0 -> Target, else Current`. The gate
reads the raw cell instead.

## The two silent consumers: both correct in ordinary play

- `games/sonic4/data/effects/ojz_effects.emp:2884` (`OJZ_Reels_Fill`) — reads the raw cell and
  walks `EditorReelBindings_OJZ_Act1`. That table is `if DEBUG == 1 { [Sec4, rates, 0] } else { [] }`
  (`effects_scenes.emp:212`): **empty in release**, so nothing depends on it there. In DEBUG on
  region 0 the walk correctly MISSES (only Sec4 is bound) and keeps `OJZ_Reel_Speed`, the
  documented fallback.
- `games/sonic4/data/generated/ojz/act1/effects_scenes.emp:175` — the same table, same walk.

Neither is reached with a wrong key in a normal frame. Both share the gate's one real (bounded)
divergence: during the 16-frame boundary lerp the raw cell names the OUTGOING scene, so a reel
binding lags a crossing by up to 16 frames while the bands are lerping between the two anyway.
DEBUG-tier, visually defensible, booked as a rider rather than a defect.

## Not done, deliberately

No fix written. Named in one sentence for whoever owns it: **the gate should read
`Parallax_Active_Config`'s rule (`Frames != 0 -> Target`) rather than the raw
`Parallax_Current_Config` cell, or settle past `PARALLAX_TRANS_DEFAULT` before sampling.**

The gate's two REDs on the declining arm are therefore false for a SECOND, independent reason
beyond `c92f7248`'s finding: the arm grades against a config that is not the one the cursor
installed.

## Provenance

- Every address derived from this build's own `s4.debug.lst`, never copied. They happen to agree
  with the reporter's (`$13FCE`, `$1486E`), which is itself a cross-check that the two builds
  carry the same content.
- `pcfg_v_deform_shift_bg` is offset `$19` (25), derived from `engine/structs.emp:384`. Read from
  this build's ROM image: `Perspective_Subtle $82`, `Perspective $80`, `Perspective_Floor $82`
  (bit 7 SET), `Perspective_Dramatic $00`, all four `EditorSceneBinding_*` `$04`. The decline IS
  authored and emitted correctly, exactly as reported.
- Instrument: `tools/aether_instance.py` (`AetherInstance`), one subprocess per run on its own
  private socket, reaped in a `finally`. No MCP call was made. No process not spawned by this run
  was signalled. Nothing in the main checkout was rebuilt or replaced.
- Wall clock at the measurements: `15:26`-`15:28` local, `up 2 days, 19:43-19:45`, load ~5.
