# S3K DAC kit survey — content-pass prep (2026-08-10)

Prep for the user-ruled (2026-08-09) S3K drum-kit import. Source =
`/home/volence/sonic_hacks/skdisasm/Sound/DAC/` (51 unique WAVs, 8-bit mono,
native rates baked in the files) + `sonic3k.macros.asm:308-476` (`DAC_Setup`
table: id → source sample + rate multiplier). Import mechanics already exist:
`tools/import_s3k_dac.py::wav_to_raw8(path, pitch_ratio=...)` resamples to the
fixed ENGINE_DAC_HZ = 18356 and bakes pitch (R9 ruling: our DAC rate does NOT
change; S3K audio is resampled to us).

## Already imported (HCZ2 phase 5) — 6 of the kit

`s3k_kick` ($81), `s3k_snare` ($86), `s3k_hitom/midtom/lowtom/floortom`
($82-$85 group at multipliers 1.0/0.80/0.67/0.58). Present in
`games/sonic4/data/sound/dac/` + `engine/sound/dac_sample_tab.emp` (entries
5-10) + `games/sonic4/data/sound/dac_banks.emp`.

## Remaining kit: ids $87..$C4 (minus the six above)

Multi-id groups share one WAV; each id bakes its own `.pcm` at its multiplier
(tom precedent). Groups + multipliers (1.0 unless noted):

| ids | file | multipliers |
|---|---|---|
| $87,$88,$89 | 87/88/89.wav | 1.0 each |
| $8A,$8B | 8A-8B.wav | 1.0 / 0.82 |
| $8C | 8C.wav | 1.0 |
| $8D,$8E | 8D-8E.wav | 1.0 / 0.77 |
| $8F | 8F.wav | 1.0 |
| $90-$93 | 90-93.wav | 1.0 / 0.78 / 0.66 / 0.56 |
| $94-$97 | 94-97.wav | 1.0 / 0.79 / 0.70 / 0.58 |
| $98-$9A | 98-9A.wav | 1.0 / 0.73 / 0.66 |
| $9B-$A1 | 9B..A1.wav | 1.0 each |
| $A2-$AC | A2..AC.wav | 1.0 each |
| $AD,$AE | AD-AE.wav | 1.0 / 0.76 |
| $AF,$B0 | AF-B0.wav | 1.0 / 0.68 |
| $B1 | B1.wav | 1.0 |
| $B2,$B3 | B2-B3 (S&K).wav (S3 variant exists too) | 1.0 / 0.76 |
| $B4,$C1-$C4 | B4C1-C4.wav | 1.0 / 0.88 / 0.82 / 0.78 / 1.04 |
| $B5-$C0 | B5..C0.wav | 1.0 each (B8/B9 share B8-B9.wav at 1.0/1.0) |

`Unused.wav` — skip. `deltas.bin` / `generated/*.dpcm` are the DPCM-encoded
forms — we import from the decoded WAVs, not these.

## Size / banking

Unique samples resampled at 1.0 ≈ 270 KB; with per-id pitch-variant baking
(ratio < 1 makes samples LONGER: len = n·18356/(rate·ratio)) expect ~350-400 KB
total. This SPANS many Z80 banks (32 KB each): per-sample `ds_bank` supports it,
but each sample must fit within one bank window (`ds_ptr`+`ds_length` < $8000,
no boundary crossing) — the data authoring needs per-bank packing + per-bank
guards (extend the current single-bank guard per pkg-3 runbook step 3).
ROM cost fine (ROM at ~10% of 4 MB). Table cost: ~60 new 12-byte descriptors,
banked data (NOT resident Z80 — the 3-byte blob headroom is untouched).

## Verification plan (house rule: rendered audio, not registers)

Per drum id: trigger via `Sound_PlaySample`, VGM capture → vgm2wav, compare
energy+spectrum against the skdisasm WAV resampled to the same pitch
(scriptable batch; spot-check a subset by ear/screenshot of spectra). The
config-a hotkeys shape or the correct-mailbox post (see
`notes/2026-08-10-silent-music-adjudication.md`) both work as trigger routes.

## Open item for execution

Exact roster = full kit $87-$C4 as above (faithful reading of the ruling) vs a
song-driven subset — going full kit unless the user trims it; per-id sample ids
in OUR table are 1-based indexes, so the S3K $8x ids map via a documented
id-mapping table in the import commit.
