# MschA2V Agent (Phase 2 — not implemented)

This directory is a placeholder for a future graph-introspecting,
natural-language prompt-writing agent. It is **not implemented** in this
release; `stub.py` contains only signatures that raise
`AgentNotImplementedError`, and nothing in the node/route/frontend layer
calls into this package.

## Planned mission

Let a creator describe intent in natural language ("make the drop hit
harder", "give the bridge a slow-motion feel", "match the chorus prompt to
the intro but at night") and have the agent:

1. Read the current `Schedule` (from the Sequencer node's `schedule_json`).
2. Introspect the surrounding ComfyUI graph — what model/resolution/sampler
   settings are actually wired into `MschA2V_BeatKSampler`, so suggestions
   are grounded in what will actually render, not guessed.
3. Propose edits to block prompts, timing, or grouping, expressed as a
   diffable `Schedule` JSON patch the user reviews before it's applied (never
   silently overwriting the user's authored blocks).

## Planned architecture

- **Local MCP server**, run as a ComfyUI-integrated subprocess (not a cloud
  call) so it can read the live graph state via the same aiohttp routes
  `mscha2v/server/routes.py` already exposes (plus a new
  `GET /mscha2v/graph_context` route that reports the connected model type,
  resolution, and sampler settings for the current workflow).
- **Tools exposed to the agent**, mirroring `mscha2v/core/schedule.py`'s pure
  functions so proposed edits can be validated (bucket limits, grid
  snapping, byte-for-byte prompt handling) before they're ever shown to the
  user:
  - `read_schedule(node_id) -> Schedule`
  - `propose_schedule_patch(schedule, instruction) -> ScheduleDiff`
  - `validate_schedule_patch(schedule, diff) -> list[Warning]`
- **No direct write access** to the live node graph — the agent always
  returns a proposed `Schedule` JSON for the user to accept via the
  Sequencer modal's normal Done flow, the same path a human edit takes.
- **Model**: out of scope to pin down in this stub; whatever local or
  API-based LLM the user configures, called only through the local MCP
  server, never embedded directly in node code.

## Why this is Phase 2, not now

Beat-synced timing math, H3 rendering, and the manual sequencer UI are the
load-bearing pieces a creator needs on day one and are fully implemented in
this release. A prompt-writing agent is valuable on top of that, but
depends on the `Schedule`/`ShotPlan` contracts being stable first — which
they now are (`mscha2v/core/schemas.py`). Implementing this Phase 2 module
means: an MCP server process lifecycle inside a ComfyUI custom node
(non-trivial — most existing MCP integrations assume a standalone process,
not one spawned by an image/video generation tool), a graph-context route,
and an LLM-facing tool surface with validation guarantees — each a
substantial project of its own.
