# R5 re-key flam trace — 2026-08-10 (pkg-4 rider, foreground oracle)

Rider R5 (docs/research/2026-08-08-sound-study-triage.md): possible double-attack
when `Seq_RekeySingle`'s pending `SCF_REKEY` and `Sfx_Restore`'s own re-key both
fire around one steal/restore. Ruling was: trace first, fix ONLY on a confirmed
trace.

## Verdict: NOT REPRODUCED — no fix booked. Structural hazard confirmed as
## real-but-narrow; latent until a song runs MEV_PITCHENV on a stealable voice.

## Trace method (repeatable)

Canonical DEBUG on oracle. HCZ2 (song 3) started via the correct mailbox post
(param block $1CA6 = `0B 32 BB 02 A2 D4`, trigger $1F02=3 — see
notes/2026-08-10-silent-music-adjudication.md). 13 steal/restore cycles forced by
posting FM SFX ids to `SND_REQ_SFX` $1F03 (jump $62 ×10, dash $B6 ×3) at ~0.8 s
spacing via the aether bus (`emulator/z80_write`); every post verified consumed
within 1 frame. Two VGM captures: 18 s no-SFX control + 82 s with-SFX. Scanner:
`tools/vgm_onsets.py` per-channel key-on timeline; flam = same-channel key-on
pair ≤ 1.5 frames apart.

Result: control min inter-onset gap 1.92 f, SFX-run 1.90 f, **zero pairs
≤ 1.5 f in either** (the 1.9-2.0 f pairs are the song's own 16th-note runs,
identical in the control). No restore produced a double attack.

## Structural read (why it didn't fire, and when it could)

- `Seq_RekeySingle` (sound_sequencer.emp:699-711): while `SCF_SFX_OVERRIDE` is
  set the re-key does no chip writes and **the arm deliberately stays pending**.
- `Sfx_Restore` FM path (sound_sfx.emp:1218+): clears the override and re-keys
  the held note at the exact stolen pitch (`Fm_NoteOnFreqExact`) iff KEYED —
  it does NOT consume a pending `SCF_REKEY`.
- So IF a `MEV_PITCHENV` pitch op lands on the stolen channel during the steal,
  restore re-keys old-pitch and the pending arm re-articulates the new pitch on
  the next ModUpdate frame: two attacks ~1 f apart at two pitches — R5's flam,
  exactly. The arm is only produced by `MEV_PITCHENV` (sole producer), so songs
  without pitch envelopes on stealable voices can never flam — evidently HCZ2's
  stolen voices in these windows carried no pitch op.
- NOTE for any future fix: the pending arm is partially LOAD-BEARING — it is
  what brings the channel to the *current* pitch after a steal that spanned a
  pitch op. A fix must keep the pitch correction and drop the double attack
  (e.g. restore skips its own re-key when `SCF_REKEY` is pending, letting the
  arm render the single correct attack next frame — MDSDRV's mask-key-on shape).

## Status

R5 stays OPEN as a latent, unconfirmed defect. Do not book the fix. Revisit
trigger: first song authored with FM pitch envelopes (trill/arp/env on a
stealable voice) — add a targeted repro then (author a 2-channel test song with
a continuous pitch env + fire jump SFX; the scanner above detects the flam
mechanically).
