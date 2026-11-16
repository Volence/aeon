# ChatGPT asset pipeline (Codex) — short design

**Date:** 2026-11-16
**Status:** PARKED by the owner ("jot it down for now"). Approach chosen; not planned or started.
**Builds on:** `2026-07-12-comfyui-art-pipeline-design.md` (the ingest/preview-gate loop) and
`tools/png_to_bg_override.py` (the one converter that exists: backgrounds).

## Intent

The owner wants Claude to request art from ChatGPT and get it into the game directly, with the
owner only judging results (approve or regenerate), never moving files between tools.

## Constraints found

- The installed ChatGPT is the Linux desktop app (`chatgpt-desktop`). It has no automation
  interface; third-party UI drivers exist only for macOS/Windows and break on app updates.
- **Codex CLI signed in with the owner's ChatGPT account has built-in image generation** that
  draws on the ChatGPT plan's limits (not available on the Free plan; image turns use limits
  ~3-5x faster). This is the programmatic path. Not yet installed here; plan tier to confirm.
- Converters: only backgrounds exist (`png_to_bg_override.py`: palette snap, flip-canonical
  dedup, tile budget from `vram.toml`). Foreground terrain needs collision; sprites need frames,
  mappings, DPLC and animation; UI needs its own path. Each asset type is its own converter.
- Transparency matters for sprites. Whether Codex imagegen gives real alpha is unverified; the
  OpenAI Images API does, but bills per image.

## Approaches

1. **Direct call (CHOSEN to start).** Claude runs Codex non-interactively with a prompt and an
   output path, waits, runs the converter, and shows the owner a preview to approve.
   No daemon, nothing to keep alive. Limit: only a session that knows the recipe can request.
2. **Request folder + watcher (the planned growth path).** A user service watches
   `studio/requests/`; each request file is handed to Codex; results and a log land in
   `studio/out/`. Any lane, or the owner by hand, can request art. Cost: a service to keep
   alive and requests that can stall unseen.
3. **OpenAI Images API key.** Most predictable (exact sizes, real transparency) but billed per
   image, separately from the ChatGPT plan. Kept as a fallback if Codex imagegen lacks alpha.

Rejected: automating the desktop app's UI (fragile, no Linux support).

## Design decisions

- The request is a file from day one (prompt, size, asset type, palette rule, destination,
  converter), so approach 1 and approach 2 share one format and the upgrade is only the watcher.
- Every asset passes the existing preview gate (owner approves) before it enters the build.
- Engine-legality is enforced by the converters' hard gates (palette, tile budget), never by
  the prompt alone.

## Open when this is picked up

- Owner's ChatGPT plan tier; install and sign in Codex; confirm imagegen output (size, alpha).
- **Which asset type comes first** (owner question, unanswered): backgrounds, FG terrain,
  badniks/characters, or UI. This decides the first converter to build.
