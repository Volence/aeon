# T7 capture verification — canonical-band pitch table (2026-07-02)

Code: `af82335` (generator + 2 TDD tests + regenerated `sound_tables_z80.asm`;
budget unchanged $310 free; pytest 810+2). Purity-checked 1x realtime captures.

**Gotcha that cost a re-capture:** the implementer's stash-compare budget check left
`s4.bin` built from the STASHED (old) tree — the first "T7 capture" was byte-identical
to T6 (proven by $A4 block-bit histograms). Always rebuild after an agent lands before
capturing. The stale-ROM check (block histogram diff) is cheap and decisive.

## HCZ2 66s vs `s3k_hcz2_ref.vgm`

**Depth (vib_series), the C.c gate — encoding-class gap CLOSED:**

| ch | ref depth c | T7 | T6 (pre) |
|---|---|---|---|
| FM1 | 36.6 | **36.7** | 19.2 |
| FM3 | 18.0 | 18.0 | 18.0 |
| FM4 | 13.6 | 13.5 | 13.5 |
| FM0/FM2 | 40.3/40.1 | 36.2/36.3 | 36.2/36.3 |

FM1 (the mismatched-encoding channel) doubled to exact ref parity. FM0/FM2 hold a
~4c/10% residue unchanged from T6 — their notes sit in the [1024,1288) band-overlap
region (encoding unchanged by the renorm), so this is NOT a table artifact; residue
noted for the T12 matrix. Small positive troughs (med -pk +4.5..+10.7 vs ref 0.0)
are the coarser cents-per-delta quantization at the new band floor; contour remains
unipolar-up, zero down-starts, exact vib-note counts (28/72 vs ref 28/71).

**Delay (gate_vib) and retrigger unchanged:** flat frames 6.9-14.0 (= T6 = ref),
retrigger 100% all channels.

**Pitch identity (rendered, melody_cmp):** bed RMS -0.1 dB vs ref, per-channel RMS
exact (FM0 -24.0 vs -24.0, FM1 -18.2 vs -18.2), FM0 tail silence 46.6% vs ref 46.3%
(improved from T5's 53.7%). A wrong table would shift everything audibly; nothing
shifted. Block-bit histogram of $A4 writes redistributed exactly per the table diff
(block-1 entries vanished into the +1 shift; overlap/floor entries unchanged).

## MT invariance (static proof + runtime corroboration)

MT is NOTE_RAW (bypasses FmPitchTableZ, sound_sequencer.asm:1144) and its melodic
path reads `MovingTrucks_PitchTable` — a separate 132-entry table not emitted by
gen_sound_tables (sound_fm.asm:645,668); the regen diff shows it untouched. Runtime:
first 8 boot+song-start FM writes byte-identical T6 vs T7 (full-length runtime A/B
was park-truncated, see gotchas below — the static proof is the load-bearing check).

## SFX (Fm_NoteOn DOES read the table)

T5-recipe capture (HCZ2 + 4x B + tail) vs the T5 capture: every band within
±0.8 dB, overall RMS -0.2 dB, centroid +35 Hz, retrigger 100% — decoded-frequency
identity (the ±2-cent TDD test) holds audibly; no octave artifacts.

## Emulator gotchas discovered this round (also in phase_notes.md)

- Parks are NOT reload-only: the A-press (MT start = heavy Z80 handshake burst)
  reliably seeds a ~20-25e9 ns park mid-session, and draining can RE-SEED a bigger
  park when the queued handshake finally executes (observed 3.4e9 → 76.9e9 → 80e9
  thrash loop). UP/B presses have been park-safe all session.
- A deadlocked oracle_gui can survive plain pkill → two instances contend for the
  socket (the handoff's warned failure mode). Use `pkill -9 -x oracle_gui` and
  verify `pgrep | wc -l` == 1 before relaunch.
- The floorTime absolute-time stamping in MDBusArbiter::ClampHandshakeTimeDeterministic
  is now the single biggest workflow cost. T8/T9 are capture/profiler-heavy —
  RECOMMEND fixing it (clamp/flush at reload + at handshake seams) as the next
  oracle micro-round BEFORE T9. Needs user sign-off (the approved micro-round is spent).
