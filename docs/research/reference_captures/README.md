# Reference captures

Ground-truth audio references for fidelity A/B work. **Verify a capture's identity
against the actual song content before using it as a reference** — a wrong/contaminated
reference caps every match and masquerades as engine bugs (this bit us twice).

| File | What it is | Trust |
|---|---|---|
| `mt_ref.vgm` | **THE authoritative Moving Trucks reference** — GD3-tagged rip ("Moving Trucks / The Adventures of Batman and Robin / Jesper Kyd"), 158.6s, NTSC clock, starts at the true song start. Every 2026-07-01 MT fix (semitone, gates, carrier TLs, LFO) was verified against this file. Note: the rip time-compresses ~4 opening onsets to t=0 — skip that artifact when aligning. | Authoritative |
| `br_moving_trucks_oracle.vgm` | Oracle capture of the B&R ROM (2026-06-19), 213.9s. Genuine MT content but starts mid-song, parts sit on rotated channels vs mt_ref, and the capture ran ~14% slow (lagging). | Content-ID only — never for pitch/tempo A/B |
| `br_moving_trucks_onsets.csv` | Onset extraction from the oracle capture (tools/vgm_onsets.py). | Same caveats as its source |

Deleted 2026-07-01: `br_mt_from_start.vgm` — forensics proved its content was NOT
Moving Trucks' opening (contaminated capture); it caused a phantom "missing intro"
hunt. Do not resurrect without re-verifying identity.
